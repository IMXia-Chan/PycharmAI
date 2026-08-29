"""后端主服务:FastAPI + DeepSeek AI + 内置规则兜底 + 存储。

启动:
    uvicorn main:app --host 127.0.0.1 --port 8000
(在 backend/ 目录下运行,或:uvicorn backend.main:app)
"""
from __future__ import annotations

import base64
import json
import logging
import secrets
import time
from typing import Optional

import httpx
import uvicorn
from fastapi import Depends, FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pathlib import Path

from . import ai, config, pdf_export, prompts, rules
from .models import (
    AnalyzeResult,
    ChatIn,
    ChatResult,
    CodeInput,
    CodeResult,
    CompareInput,
    CompareResult,
    Library,
    LibraryIn,
    LibraryItem,
    LibraryItemIn,
    Note,
    NoteIn,
    Record,
    RecordIn,
    SearchResult,
    Snippet,
    SnippetIn,
    TextIn,
    TextResult,
)
from .storage import get_storage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("backend")

app = FastAPI(title="Python 代码助手后端", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def _validation_error_handler(request: Request, exc: RequestValidationError):
    """422 时打印原始请求体,方便排查插件与后端字段不一致。"""
    raw = await request.body()
    logger.error("422 校验失败 | body=%s | errors=%s", raw.decode("utf-8", "ignore"), exc.errors())
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


# ---------- 每请求身份 / API key ----------

def _api_key(x_api_key: Optional[str] = Header(None, alias="X-API-Key")) -> str:
    """插件本机保存的 DeepSeek API key,随每次请求带来。"""
    return (x_api_key or "").strip()


def _identity(
    x_username: Optional[str] = Header(None, alias="X-Username"),
    x_token: Optional[str] = Header(None, alias="X-Token"),
) -> tuple[str, str]:
    """云端多用户身份:用户名 + 令牌。插件侧已 Base64 编码,这里解码;旧版明文则原样返回。"""
    return _decode_header(x_username), _decode_header(x_token)


def _decode_header(v: Optional[str]) -> str:
    if not v:
        return ""
    try:
        return base64.b64decode(v).decode("utf-8")
    except Exception:  # noqa: BLE001
        return v.strip()


# ---------- 工具 ----------

def _parse_json(text: str, fallback: dict) -> dict:
    """把 AI 返回的文本解析成 JSON,失败则返回兜底结构。"""
    try:
        text = text.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text)
    except Exception as e:  # noqa: BLE001
        logger.warning("AI 返回 JSON 解析失败:%s", e)
        return fallback


def _analyze_prompt(code: str, line: int) -> str:
    """把全文(带行号)拼给 AI,并标注当前编辑行,便于定位跨行问题。"""
    out = []
    for i, ln in enumerate(code.splitlines(), start=1):
        mark = "  <-- 当前编辑行" if i == line else ""
        out.append(f"{i:>4} | {ln}{mark}")
    return "代码(带行号):\n" + "\n".join(out)


# ---------- 健康检查 ----------

@app.get("/health")
def health():
    return {
        "status": "ok",
        "ai": ai.is_available(),
        "cloud": bool(config.CLOUD_URL),
    }


# ---------- 网页版 UI(问答 + 中文搜索) ----------

_WEB_HTML = Path(__file__).parent / "web" / "index.html"

# 网页入口令牌:只有插件能拿到令牌再打开 /web,直接敲浏览器地址进不来。
# 令牌一次性使用、120 秒过期,页面打开即作废——刷新或重进都必须重新走插件。
_web_tokens: dict[str, float] = {}
_WEB_TOKEN_TTL = 120


def _prune_web_tokens() -> None:
    now = time.time()
    for t in [t for t, exp in _web_tokens.items() if exp < now]:
        _web_tokens.pop(t, None)


@app.get("/api/web/open")
def web_open():
    """插件专用:生成一次性入口令牌,拿到令牌才能打开网页端。"""
    _prune_web_tokens()
    token = secrets.token_urlsafe(24)
    _web_tokens[token] = time.time() + _WEB_TOKEN_TTL
    return {"token": token}


def _web_html() -> HTMLResponse:
    try:
        resp = HTMLResponse(content=_WEB_HTML.read_text(encoding="utf-8"))
    except FileNotFoundError:
        resp = HTMLResponse(
            content="<h1>网页未找到</h1><p>缺少 backend/web/index.html</p>", status_code=404
        )
    resp.headers["Cache-Control"] = "no-store"
    return resp


def _web_no_entry() -> HTMLResponse:
    resp = HTMLResponse(
        content=(
            "<h1>请从插件进入</h1>"
            "<p>这个网页是私有的,只能通过插件的「网页端 AI 深度搜索」打开。</p>"
            "<p>请回到 PyCharm,点菜单里的「网页端 AI 深度搜索」(或按 Ctrl+Alt+A)。</p>"
        ),
        status_code=403,
    )
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.get("/web")
def web_ui(token: Optional[str] = None):
    """入口:必须带插件刚生成的一次性令牌;令牌用掉即作废,刷新/重进都要重新走插件。"""
    _prune_web_tokens()
    if token and token in _web_tokens:
        _web_tokens.pop(token, None)
        return _web_html()
    return _web_no_entry()


@app.get("/api/version")
def plugin_version():
    """转发云端的最新版本信息;云端不可用/未配置时返回空(插件据此不提示)。"""
    if not config.CLOUD_URL:
        return {"version": "", "message": "", "url": ""}
    try:
        r = httpx.get(f"{config.CLOUD_URL}/version", timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception as e:  # noqa: BLE001
        logger.warning("查询最新版本失败:%s", e)
    return {"version": "", "message": "", "url": ""}


@app.post("/api/verify")
def verify(api_key: str = Depends(_api_key)):
    """轻量连通性验证:让模型只回 'ok',用于插件启动时确认 API key 有效。"""
    if not ai.is_available(api_key):
        return {"ok": False, "error": "未配置 API key"}
    try:
        reply = ai.chat(
            system="你是连通性测试,只回复两个字:ok", user="ping",
            max_tokens=4, api_key=api_key,
        )
        return {"ok": True, "reply": reply.strip()}
    except Exception as e:  # noqa: BLE001
        msg = str(e)
        if "401" in msg or "invalid" in msg.lower() or "authentication" in msg.lower():
            return {"ok": False, "error": "API key 无效或已失效,请重新生成"}
        return {"ok": False, "error": msg[:200]}


# ---------- 功能2:输入时检测常见错误 ----------

@app.post("/api/analyze", response_model=AnalyzeResult)
def analyze(body: CodeInput, deep: Optional[bool] = None, api_key: str = Depends(_api_key)):
    """检测代码中的错误/不规范写法。

    - 始终运行内置规则(快,离线可用)
    - deep=True 且配置了 API key 时,追加 AI 深度分析(含跨行问题,如变量未定义)
    """
    code = body.code or ""
    line = body.line or 0
    rule_issues = rules.check_code(code)

    source = "rules"
    ai_issues: list[dict] = []
    use_ai = (deep if deep is not None else True) and ai.is_available(api_key)
    if use_ai and code.strip():
        try:
            raw = ai.chat(prompts.ANALYZE_SYSTEM, _analyze_prompt(code, line), temperature=0.2, json_mode=True, api_key=api_key)
            data = _parse_json(raw, {"issues": []})
            ai_issues = data.get("issues", []) if isinstance(data, dict) else []
            source = "ai"
        except Exception as e:  # noqa: BLE001
            logger.warning("AI 分析失败,退回规则:%s", e)

    # 合并:AI 在前,按 (标题, 行号) 去重
    seen = set()
    merged: list[dict] = []
    for it in ai_issues + rule_issues:
        if not isinstance(it, dict):
            continue
        title = (it.get("title") or "").strip()
        try:
            line_no = int(it.get("line") or 0)
        except (TypeError, ValueError):
            line_no = 0
        key = (title, line_no)
        if key in seen:
            continue
        seen.add(key)
        it["line"] = line_no
        merged.append(it)

    return AnalyzeResult(issues=merged, source=source)


# ---------- 功能1:记录不规范代码 + 云端文件库 + AI 笔记 ----------

@app.post("/api/record", response_model=Record)
def record(body: RecordIn, api_key: str = Depends(_api_key), identity: tuple[str, str] = Depends(_identity)):
    """记录一条不规范/错误代码,并做 AI 深度分析(若可用)。"""
    rec = body.model_dump()
    rec["ai_analysis"] = ""
    # 解释代码 / 报错解释的记录已自带解释(在 message 里),无需再跑一次重复 AI 分析
    skip_ai = body.category in ("explain", "error-explain")
    if ai.is_available(api_key) and body.code.strip() and not skip_ai:
        try:
            raw = ai.chat(prompts.ANALYZE_SYSTEM, body.code, temperature=0.3, json_mode=True, api_key=api_key)
            data = _parse_json(raw, {"issues": []})
            issues = data.get("issues", []) if isinstance(data, dict) else []
            if issues:
                rec["ai_analysis"] = json.dumps(issues, ensure_ascii=False)
                # 用第一个问题的标题/分类回填,便于列表展示
                first = issues[0]
                rec.setdefault("title", first.get("title", ""))
                rec.setdefault("category", first.get("category", "unknown"))
        except Exception as e:  # noqa: BLE001
            logger.warning("AI 分析失败:%s", e)
    stored = get_storage().add_record(rec, identity[0], identity[1])
    return Record(**stored)


@app.get("/api/records", response_model=list[Record])
def list_records(limit: int = 50, identity: tuple[str, str] = Depends(_identity)):
    return [Record(**r) for r in get_storage().list_records(limit, identity[0], identity[1])]


@app.post("/api/records/upload")
def upload_records(body: dict, identity: tuple[str, str] = Depends(_identity)):
    """插件「候选库」一键上传:把选中的本地记录(文件)批量追加到网页端记录库。

    只追加、不清空;保留 filename,网页端按文件名分组即可看出每条记录来自哪个源文件。
    """
    recs = body.get("records", [])
    n = 0
    for r in recs:
        if not isinstance(r, dict):
            continue
        get_storage().add_record(
            {
                "code": r.get("code", ""),
                "filename": r.get("filename", ""),
                "line": r.get("line", 0),
                "title": r.get("title", ""),
                "message": r.get("message", ""),
                "category": r.get("category", "unknown"),
                "severity": r.get("severity", "info"),
            },
            identity[0], identity[1],
        )
        n += 1
    return {"ok": True, "count": n}


@app.post("/api/notes/generate", response_model=Note)
def generate_note(api_key: str = Depends(_api_key), identity: tuple[str, str] = Depends(_identity)):
    """根据最近的记录,用 AI 生成一份学习笔记并保存。"""
    if not ai.is_available(api_key):
        raise _http_ai_unavailable()
    records = get_storage().list_records(30, identity[0], identity[1])
    if not records:
        return Note(id="", title="暂无记录", content="还没有积累到代码记录,先写点代码吧。", created_at="")

    lines = []
    for r in records:
        lines.append(
            f"- [{r.get('category')}/{r.get('severity')}] {r.get('title') or r.get('message')} "
            f"| 代码:{r.get('code', '').strip()[:120]}"
        )
    user = "以下是近期不规范/错误的代码记录:\n" + "\n".join(lines)
    try:
        content = ai.chat(prompts.NOTE_SYSTEM, user, temperature=0.4, max_tokens=800, api_key=api_key)
    except Exception as e:  # noqa: BLE001
        logger.warning("生成笔记失败:%s", e)
        content = "AI 笔记生成失败,请检查 DeepSeek API key。"
    storage = get_storage()
    # 只保留最新一份「AI 学习笔记」:生成前删掉旧的,避免点一次堆一条
    for old in storage.list_notes(100, identity[0], identity[1]):
        if old.get("title") == "AI 学习笔记":
            storage.delete_note(old["id"], identity[0], identity[1])
    note = storage.add_note({"title": "AI 学习笔记", "content": content}, identity[0], identity[1])
    return Note(**note)


@app.get("/api/notes", response_model=list[Note])
def list_notes(limit: int = 20, identity: tuple[str, str] = Depends(_identity)):
    return [Note(**n) for n in get_storage().list_notes(limit, identity[0], identity[1])]


@app.delete("/api/notes/{note_id}")
def delete_note(note_id: str, identity: tuple[str, str] = Depends(_identity)):
    """删除一条学习笔记(直接删本地笔记库)。"""
    ok = get_storage().delete_note(note_id, identity[0], identity[1])
    return {"ok": ok}


@app.post("/api/notes", response_model=Note)
def add_note(body: NoteIn, identity: tuple[str, str] = Depends(_identity)):
    """手动保存一条笔记(问答/搜索/对比的结果都能存进来)。"""
    note = get_storage().add_note(
        {"title": body.title or "学习笔记", "content": body.content},
        identity[0], identity[1],
    )
    return Note(**note)


@app.get("/api/notes/export")
def export_notes(format: str = "pdf", api_key: str = Depends(_api_key), identity: tuple[str, str] = Depends(_identity)):
    """深度分析 + 导出笔记。format=pdf 导出 PDF,format=md 导出 Markdown。"""
    storage = get_storage()
    records = storage.list_records(100, identity[0], identity[1])
    notes = storage.list_notes(20, identity[0], identity[1])

    deep = ""
    if ai.is_available(api_key) and records:
        try:
            lines = []
            for r in records:
                lines.append(
                    f"- [{r.get('category')}/{r.get('severity')}] {r.get('title') or r.get('message')}"
                    f" | {r.get('code', '').strip()[:200]}"
                )
            deep = ai.chat(
                prompts.DEEP_ANALYSIS_SYSTEM,
                "近期错误记录:\n" + "\n".join(lines),
                temperature=0.4, max_tokens=1500, api_key=api_key,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("深度分析失败:%s", e)

    if format == "md":
        md_text = pdf_export.build_markdown(deep, notes, records)
        return Response(
            content=md_text.encode("utf-8"),
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="python-study-notes.md"'},
        )

    try:
        pdf_bytes = pdf_export.build_pdf(deep, notes, records)
    except Exception as e:  # noqa: BLE001
        logger.error("生成 PDF 失败:%s", e)
        return JSONResponse(status_code=500, content={"detail": f"生成 PDF 失败:{e}"})

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="python-study-notes.pdf"'},
    )


# ---------- 文件库(笔记页第二层,最多 5 个) ----------

_MAX_LIBRARIES = 5


@app.get("/api/libraries", response_model=list[Library])
def list_libraries(identity: tuple[str, str] = Depends(_identity)):
    return [Library(**l) for l in get_storage().list_libraries(identity[0], identity[1])]


@app.post("/api/libraries", response_model=Library)
def create_library(body: LibraryIn, identity: tuple[str, str] = Depends(_identity)):
    """创建一个文件库,最多 5 个。"""
    storage = get_storage()
    if len(storage.list_libraries(identity[0], identity[1])) >= _MAX_LIBRARIES:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="最多只能创建 5 个文件库")
    lib = storage.add_library({"name": body.name.strip() or "文件库"}, identity[0], identity[1])
    return Library(**lib)


@app.delete("/api/libraries/{library_id}")
def delete_library(library_id: str, identity: tuple[str, str] = Depends(_identity)):
    """删除一个文件库(连同其条目)。"""
    ok = get_storage().delete_library(library_id, identity[0], identity[1])
    return {"ok": ok}


@app.post("/api/libraries/{library_id}/items", response_model=LibraryItem)
def add_library_item(library_id: str, body: LibraryItemIn, identity: tuple[str, str] = Depends(_identity)):
    """拖拽落库:添加一条条目(kind=note 笔记 / kind=file 文件)。"""
    item = get_storage().add_library_item(
        library_id,
        {"kind": body.kind or "note", "ref_id": body.ref_id, "title": body.title, "content": body.content},
        identity[0], identity[1],
    )
    return LibraryItem(**item)


@app.delete("/api/libraries/{library_id}/items/{item_id}")
def delete_library_item(library_id: str, item_id: str, identity: tuple[str, str] = Depends(_identity)):
    ok = get_storage().delete_library_item(library_id, item_id, identity[0], identity[1])
    return {"ok": ok}


def _library_records(storage, items: list[dict], identity: tuple[str, str]) -> list[dict]:
    """取该文件库里 file 条目对应的错误记录(按文件名匹配)。"""
    filenames = {it.get("title") for it in items if it.get("kind") == "file" and it.get("title")}
    return [
        r for r in storage.list_records(1000, identity[0], identity[1])
        if (r.get("filename") or "未命名文件") in filenames
    ]


@app.post("/api/libraries/{library_id}/generate", response_model=LibraryItem)
def generate_library_note(library_id: str, api_key: str = Depends(_api_key), identity: tuple[str, str] = Depends(_identity)):
    """根据该文件库里的文件(错误记录),用 AI 生成一份库专属笔记。"""
    storage = get_storage()
    lib = next((l for l in storage.list_libraries(identity[0], identity[1]) if l["id"] == library_id), None)
    lib_name = (lib or {}).get("name") or "文件库"
    items = (lib or {}).get("items", [])

    records = _library_records(storage, items, identity)
    if not records:
        return LibraryItem(
            id="", library_id=library_id, kind="note", ref_id="",
            title=f"{lib_name} · AI 笔记",
            content="这个文件库还没有拖入任何文件。先从下方「错误记录」里把文件拖进来,再点「生成笔记」。",
            created_at="",
        )
    if not ai.is_available(api_key):
        raise _http_ai_unavailable()

    lines = [
        f"- [{r.get('category')}/{r.get('severity')}] {r.get('title') or r.get('message')} "
        f"| 代码:{r.get('code', '').strip()[:120]}"
        for r in records
    ]
    user = f"以下是文件库「{lib_name}」里的错误/不规范代码记录:\n" + "\n".join(lines)
    try:
        content = ai.chat(prompts.NOTE_SYSTEM, user, temperature=0.4, max_tokens=800, api_key=api_key)
    except Exception as e:  # noqa: BLE001
        logger.warning("生成库笔记失败:%s", e)
        content = "AI 笔记生成失败,请检查 DeepSeek API key。"

    # 只保留最新一份库专属生成笔记:删掉旧的 ref_id 为空的 note 条目
    for it in items:
        if it.get("kind") == "note" and not it.get("ref_id"):
            storage.delete_library_item(library_id, it["id"], identity[0], identity[1])

    item = storage.add_library_item(
        library_id,
        {"kind": "note", "ref_id": "", "title": f"{lib_name} · AI 笔记", "content": content},
        identity[0], identity[1],
    )
    return LibraryItem(**item)


@app.get("/api/libraries/{library_id}/export")
def export_library(library_id: str, format: str = "pdf", identity: tuple[str, str] = Depends(_identity)):
    """导出某个文件库(它的笔记条目 + 文件条目对应的错误记录)。format=pdf 或 md。"""
    storage = get_storage()
    lib = next((l for l in storage.list_libraries(identity[0], identity[1]) if l["id"] == library_id), None)
    if lib is None:
        return JSONResponse(status_code=404, content={"detail": "文件库不存在"})
    lib_name = lib.get("name") or "文件库"
    items = lib.get("items", [])

    notes = [
        {"title": it.get("title") or "学习笔记", "content": it.get("content") or ""}
        for it in items if it.get("kind") == "note"
    ]
    records = _library_records(storage, items, identity)

    # Content-Disposition 的 filename 只接受 latin-1 字符,中文库名转成 ASCII 安全文件名(中文名由前端 download 属性承载)
    ascii_name = "".join(ch for ch in lib_name if ch.isascii() and (ch.isalnum() or ch in "-_.")).strip("-_.") or "library"
    if format == "md":
        md_text = pdf_export.build_markdown("", notes, records, title=lib_name)
        return Response(
            content=md_text.encode("utf-8"),
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{ascii_name}-notes.md"'},
        )
    try:
        pdf_bytes = pdf_export.build_pdf("", notes, records, title=lib_name)
    except Exception as e:  # noqa: BLE001
        logger.error("生成文件库 PDF 失败:%s", e)
        return JSONResponse(status_code=500, content={"detail": f"生成 PDF 失败:{e}"})
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{ascii_name}-notes.pdf"'},
    )


# ---------- 功能3:中文描述 → 函数/指令 ----------

@app.post("/api/search-functions", response_model=SearchResult)
def search_functions(body: CodeInput, api_key: str = Depends(_api_key)):
    """用中文自然语言描述需求,返回候选函数/指令。"""
    query = (body.code or "").strip()
    if not query:
        return SearchResult(candidates=[])
    # 常见操作先用内置关键词表精确命中,保证「排序/去重/遍历/大小写」等一定答对
    kw = _keyword_search(query)
    if kw:
        return SearchResult(candidates=kw)
    if not ai.is_available(api_key):
        return SearchResult(candidates=[])
    try:
        raw = ai.chat(prompts.SEARCH_SYSTEM, query, temperature=0.3, json_mode=True, api_key=api_key)
        data = _parse_json(raw, {"candidates": []})
        cands = data.get("candidates", []) if isinstance(data, dict) else []
        return SearchResult(candidates=cands)
    except Exception as e:  # noqa: BLE001
        logger.warning("函数搜索失败:%s", e)
        return SearchResult(candidates=[])


def _keyword_search(query: str) -> list[dict]:
    """内置关键词精确匹配:常见操作一定返回正确结果,AI 只兜底长尾查询。

    顺序=命中优先级,更具体的词放前面。命中多个词时合并去重,最多 5 个。
    """
    table = [
        # 大小写 / 字符串
        ("大写", [
            {"name": "str.upper", "signature": "str.upper()", "module": "builtins", "description": "把字符串全部转成大写"},
            {"name": "str.capitalize", "signature": "str.capitalize()", "module": "builtins", "description": "首字母大写、其余小写"},
        ]),
        ("小写", [
            {"name": "str.lower", "signature": "str.lower()", "module": "builtins", "description": "把字符串全部转成小写"},
            {"name": "str.casefold", "signature": "str.casefold()", "module": "builtins", "description": "更激进的小写,适合忽略大小写比较"},
        ]),
        ("去重", [
            {"name": "set", "signature": "set(iterable)", "module": "builtins", "description": "集合,元素唯一,天然去重"},
            {"name": "dict.fromkeys", "signature": "dict.fromkeys(iterable)", "module": "builtins", "description": "用键去重且保留顺序"},
        ]),
        ("重复", [
            {"name": "set", "signature": "set(iterable)", "module": "builtins", "description": "集合去重"},
            {"name": "dict.fromkeys", "signature": "dict.fromkeys(iterable)", "module": "builtins", "description": "保留顺序去重"},
        ]),
        ("排序", [
            {"name": "sorted", "signature": "sorted(iterable, key=None, reverse=False)", "module": "builtins", "description": "返回排序后的新列表,不改变原列表"},
            {"name": "list.sort", "signature": "list.sort(key=None, reverse=False)", "module": "builtins", "description": "就地排序,改变原列表"},
            {"name": "reversed", "signature": "reversed(sequence)", "module": "builtins", "description": "返回反向迭代器(倒序)"},
        ]),
        ("下标", [
            {"name": "enumerate", "signature": "enumerate(iterable, start=0)", "module": "builtins", "description": "遍历时同时得到下标与元素"},
        ]),
        ("遍历", [
            {"name": "for", "signature": "for item in iterable:", "module": "builtins", "description": "遍历每个元素"},
            {"name": "enumerate", "signature": "enumerate(iterable, start=0)", "module": "builtins", "description": "遍历时同时拿到下标"},
            {"name": "range", "signature": "range(stop)", "module": "builtins", "description": "生成整数序列"},
        ]),
        ("循环", [
            {"name": "for", "signature": "for item in iterable:", "module": "builtins", "description": "循环遍历"},
            {"name": "while", "signature": "while condition:", "module": "builtins", "description": "条件循环"},
        ]),
        ("正则", [
            {"name": "re.search", "signature": "re.search(pattern, string)", "module": "re", "description": "搜索第一个匹配"},
            {"name": "re.findall", "signature": "re.findall(pattern, string)", "module": "re", "description": "找出所有匹配"},
        ]),
        ("读文件", [
            {"name": "open", "signature": "open(file, mode='r', encoding='utf-8')", "module": "builtins", "description": "打开并读取文件"},
            {"name": "Path.read_text", "signature": "Path('x.txt').read_text(encoding='utf-8')", "module": "pathlib", "description": "一次性读取整个文件文本"},
        ]),
        ("写文件", [
            {"name": "open", "signature": "open(file, mode='w', encoding='utf-8')", "module": "builtins", "description": "以写模式打开文件"},
            {"name": "Path.write_text", "signature": "Path('x.txt').write_text(s, encoding='utf-8')", "module": "pathlib", "description": "一次性写入文本"},
        ]),
        ("统计", [
            {"name": "collections.Counter", "signature": "Counter(iterable)", "module": "collections", "description": "统计每个元素出现次数"},
            {"name": "str.count", "signature": "str.count(sub)", "module": "builtins", "description": "统计子串出现次数"},
        ]),
        ("拼接", [
            {"name": "str.join", "signature": "sep.join(iterable)", "module": "builtins", "description": "用分隔符拼接字符串"},
        ]),
        ("分割", [
            {"name": "str.split", "signature": "str.split(sep=None)", "module": "builtins", "description": "按分隔符切分字符串"},
        ]),
        ("替换", [
            {"name": "str.replace", "signature": "str.replace(old, new)", "module": "builtins", "description": "替换子串"},
        ]),
        ("查找", [
            {"name": "str.find", "signature": "str.find(sub)", "module": "builtins", "description": "查找子串位置,找不到返回 -1"},
            {"name": "in", "signature": "sub in string", "module": "builtins", "description": "判断是否包含"},
        ]),
        ("反转", [
            {"name": "reversed", "signature": "reversed(sequence)", "module": "builtins", "description": "返回反向迭代器"},
            {"name": "[::-1]", "signature": "sequence[::-1]", "module": "builtins", "description": "切片反转"},
        ]),
        ("求和", [
            {"name": "sum", "signature": "sum(iterable, start=0)", "module": "builtins", "description": "求和"},
        ]),
        ("最大", [
            {"name": "max", "signature": "max(iterable)", "module": "builtins", "description": "返回最大值"},
        ]),
        ("最小", [
            {"name": "min", "signature": "min(iterable)", "module": "builtins", "description": "返回最小值"},
        ]),
        ("长度", [
            {"name": "len", "signature": "len(obj)", "module": "builtins", "description": "返回元素个数/长度"},
        ]),
        ("过滤", [
            {"name": "filter", "signature": "filter(function, iterable)", "module": "builtins", "description": "按条件过滤元素"},
        ]),
        ("映射", [
            {"name": "map", "signature": "map(function, iterable)", "module": "builtins", "description": "对每个元素应用函数"},
        ]),
        ("随机", [
            {"name": "random.choice", "signature": "random.choice(seq)", "module": "random", "description": "随机选一个"},
            {"name": "random.randint", "signature": "random.randint(a, b)", "module": "random", "description": "随机整数"},
        ]),
        ("类型转换", [
            {"name": "int", "signature": "int(x)", "module": "builtins", "description": "转整数"},
            {"name": "float", "signature": "float(x)", "module": "builtins", "description": "转浮点数"},
            {"name": "str", "signature": "str(x)", "module": "builtins", "description": "转字符串"},
        ]),
    ]
    out: list[dict] = []
    seen: set[str] = set()
    for kw, cands in table:
        if kw in query:
            for c in cands:
                if c["name"] not in seen:
                    seen.add(c["name"])
                    out.append(c)
            if len(out) >= 5:
                break
    return out


# ---------- 功能4:相似函数对比 ----------

@app.post("/api/compare", response_model=CompareResult)
def compare(body: CompareInput, api_key: str = Depends(_api_key)):
    """对比两个函数/指令的本质区别与用法差异。"""
    a, b = (body.function_a or "").strip(), (body.function_b or "").strip()
    if not a or not b:
        return CompareResult(summary="请同时填写两个函数/指令。")
    if not ai.is_available(api_key):
        return CompareResult(
            summary="未接入 API。请在网页右上角填写你自己的 DeepSeek API key(只存本机)。"
        )
    user = f"请对比:函数 A = `{a}` 与 函数 B = `{b}`"
    try:
        raw = ai.chat(prompts.COMPARE_SYSTEM, user, temperature=0.3, json_mode=True, api_key=api_key)
        data = _parse_json(raw, {"summary": "", "differences": []})
        return CompareResult(
            summary=data.get("summary", ""),
            differences=data.get("differences", []) if isinstance(data, dict) else [],
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("对比失败:%s", e)
        return CompareResult(summary=f"对比失败:{e}")


# ---------- 功能5:AI 问答 ----------

@app.post("/api/chat", response_model=ChatResult)
def chat(body: ChatIn, api_key: str = Depends(_api_key)):
    """中文问答:直接问 Python 问题,AI 当场回答。"""
    question = (body.question or "").strip()
    if not question:
        return ChatResult(reply="")
    if not ai.is_available(api_key):
        raise _http_ai_unavailable()
    try:
        reply = ai.chat(prompts.CHAT_SYSTEM, question, temperature=0.6, max_tokens=2000, api_key=api_key)
        return ChatResult(reply=reply.strip())
    except Exception as e:  # noqa: BLE001
        logger.warning("问答失败:%s", e)
        return ChatResult(reply=f"AI 调用失败:{e}")


# ---------- 功能6:解释代码 / 生成注释 / 报错解释 / 自动修复 ----------

@app.post("/api/explain", response_model=TextResult)
def explain_code(body: CodeInput, api_key: str = Depends(_api_key)):
    """用中文解释一段代码在做什么。"""
    code = (body.code or "").strip()
    if not code:
        return TextResult(text="请先选中一段代码。")
    if not ai.is_available(api_key):
        raise _http_ai_unavailable()
    try:
        text = ai.chat(prompts.EXPLAIN_SYSTEM, code, temperature=0.3, max_tokens=1500, api_key=api_key)
        return TextResult(text=text.strip())
    except Exception as e:  # noqa: BLE001
        logger.warning("解释代码失败:%s", e)
        return TextResult(text=f"AI 调用失败:{e}")


@app.post("/api/comment", response_model=CodeResult)
def add_comments(body: CodeInput, api_key: str = Depends(_api_key)):
    """为一段代码逐行加上中文注释,返回加注释后的完整代码。"""
    code = (body.code or "").strip()
    if not code:
        return CodeResult(code="")
    if not ai.is_available(api_key):
        raise _http_ai_unavailable()
    try:
        result = ai.chat(prompts.COMMENT_SYSTEM, code, temperature=0.2, max_tokens=2000, api_key=api_key)
        return CodeResult(code=result.strip())
    except Exception as e:  # noqa: BLE001
        logger.warning("生成注释失败:%s", e)
        return CodeResult(code=f"# AI 调用失败:{e}")


@app.post("/api/explain-error", response_model=TextResult)
def explain_error(body: TextIn, api_key: str = Depends(_api_key)):
    """解释一段运行时报错的原因与改法。"""
    error = (body.text or "").strip()
    if not error:
        return TextResult(text="请先粘贴报错信息。")
    if not ai.is_available(api_key):
        raise _http_ai_unavailable()
    try:
        text = ai.chat(prompts.ERROR_SYSTEM, error, temperature=0.3, max_tokens=1500, api_key=api_key)
        return TextResult(text=text.strip())
    except Exception as e:  # noqa: BLE001
        logger.warning("报错解释失败:%s", e)
        return TextResult(text=f"AI 调用失败:{e}")


@app.post("/api/fix", response_model=CodeResult)
def fix_code(body: CodeInput, api_key: str = Depends(_api_key)):
    """找出代码中的错误并返回修复后的完整代码。"""
    code = (body.code or "").strip()
    if not code:
        return CodeResult(code="")
    if not ai.is_available(api_key):
        raise _http_ai_unavailable()
    try:
        result = ai.chat(prompts.FIX_SYSTEM, code, temperature=0.2, max_tokens=2000, api_key=api_key)
        return CodeResult(code=result.strip())
    except Exception as e:  # noqa: BLE001
        logger.warning("自动修复失败:%s", e)
        return CodeResult(code=f"# AI 调用失败:{e}")


# ---------- 功能7:代码片段库 ----------

@app.post("/api/snippets", response_model=Snippet)
def add_snippet(body: SnippetIn, identity: tuple[str, str] = Depends(_identity)):
    """保存一条代码片段(存本机,见 storage)。"""
    stored = get_storage().add_snippet(body.model_dump(), identity[0], identity[1])
    return Snippet(**stored)


@app.get("/api/snippets", response_model=list[Snippet])
def list_snippets(limit: int = 100, identity: tuple[str, str] = Depends(_identity)):
    return [Snippet(**s) for s in get_storage().list_snippets(limit, identity[0], identity[1])]


@app.delete("/api/snippets/{snippet_id}")
def delete_snippet(snippet_id: str, identity: tuple[str, str] = Depends(_identity)):
    ok = get_storage().delete_snippet(snippet_id, identity[0], identity[1])
    return {"ok": ok}


# ---------- 错误辅助 ----------

def _http_ai_unavailable():
    from fastapi import HTTPException

    return HTTPException(status_code=400, detail="未配置 DEEPSEEK_API_KEY")


# ---------- 管理员登录(转发到云端服务器) ----------

def _proxy_admin(path: str, body: dict) -> dict:
    """把管理员请求转发给云端服务器,附上服务间密钥。本地后端不存任何管理员凭据。"""
    if not config.CLOUD_URL:
        return {"ok": False, "error": "未配置云端服务器,管理员登录不可用"}
    try:
        r = httpx.post(
            f"{config.CLOUD_URL}{path}",
            json=body,
            headers={"X-Admin-Key": config.CLOUD_TOKEN},
            timeout=15,
        )
        data = r.json()
        if r.status_code == 200:
            return data
        return {"ok": False, "error": data.get("detail", f"云端返回 {r.status_code}")}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"无法连接云端:{e}"}


@app.post("/api/admin/login")
def admin_login(body: dict):
    return _proxy_admin("/admin/login", body)


@app.post("/api/admin/verify")
def admin_verify(body: dict):
    return _proxy_admin("/admin/verify", body)


if __name__ == "__main__":
    # 直接传 app 对象,避免相对导入下 import 字符串失效;开发调试用
    uvicorn.run(app, host="127.0.0.1", port=config.PORT)
