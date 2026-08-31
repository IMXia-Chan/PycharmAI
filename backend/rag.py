"""RAG 检索增强:把本地知识库的命中结果拼成上下文,喂给 DeepSeek。

复用 error_knowledge_base 的检索内核(与 kb.py 相同的导入方式),在 AI 回答报错
问题前先检索知识库(公共 + 个人),把 top_k 条命中的「报错类型 + 报错信息 + 解决方案」
格式化成一段中文上下文,拼进 system prompt,让回答被真实案例增强。

对外只有一个函数 build_kb_context(query, top_k),无命中返回空串。
"""
from __future__ import annotations

import re
import sys
from dataclasses import asdict
from pathlib import Path

# 复用 error_knowledge_base 的 core(检索内核 / 存储)
_KB_DIR = Path(__file__).resolve().parent.parent / "error_knowledge_base"
if str(_KB_DIR) not in sys.path:
    sys.path.insert(0, str(_KB_DIR))

from core.searcher import Searcher  # noqa: E402
from core.storage import PrivateDatabase, PublicDatabase  # noqa: E402

# 每条命中里 solution / error_message 的截断长度,防止 context 过长爆 token
_SOLUTION_MAX = 300
_MESSAGE_MAX = 200
_DEFAULT_TOP_K = 3

# source 形如 `{域名}/{数字id}`(Stack Exchange 爬虫写入)时,可拼回原帖链接
_SE_SOURCE_RE = re.compile(r"^(.+)/(\d+)$")


def _fmt_source(d: dict) -> str:
    """把记录的来源字段格式化成可读文本(公共库 source / 个人库 file_path)。"""
    source = str(d.get("source") or "")
    m = _SE_SOURCE_RE.match(source)
    if m:
        return f"https://{m.group(1)}/questions/{m.group(2)}"
    if source:
        return source
    file_path = str(d.get("file_path") or "")
    return f"本地文件 {file_path}" if file_path else "本地个人库"


def _truncate(text: str, limit: int) -> str:
    """截断到 limit 字符,超出加省略号。"""
    text = (text or "").strip()
    return text if len(text) <= limit else text[:limit] + " …"


def _format_hit(idx: int, hit) -> str:
    """把一条 SearchHit 格式化成一段【案例N】文本。"""
    d = asdict(hit.record)
    error_type = str(d.get("error_type") or "未知错误")
    message = _truncate(str(d.get("error_message") or ""), _MESSAGE_MAX)
    solution = _truncate(str(d.get("solution") or ""), _SOLUTION_MAX)
    parts = [f"【案例{idx}】类型: {error_type}"]
    if message:
        parts.append(f"报错: {message}")
    if solution:
        parts.append(f"解决: {solution}")
    parts.append(f"来源: {_fmt_source(d)}")
    return "\n".join(parts)


def build_kb_context(query: str, top_k: int = _DEFAULT_TOP_K) -> str:
    """检索本地知识库,返回格式化的上下文文本;无命中返回空串。

    query: 检索关键词(用户问题 / 报错文本 / 代码)
    top_k: 最多取几条命中(合并公共库 + 个人库后按相关度降序取前 top_k 条)
    """
    if not (query or "").strip():
        return ""
    try:
        result = Searcher(PublicDatabase(), PrivateDatabase()).search_all(query)
    except Exception:
        # 知识库不可用不阻塞主流程:当作无命中
        return ""

    merged = list(result.get("public", [])) + list(result.get("private", []))
    if not merged:
        return ""
    # 两库各自已按 score 降序,合并后再排一次取 top_k
    merged.sort(key=lambda h: h.score, reverse=True)
    top = merged[:top_k]
    if not top:
        return ""

    lines = [
        "以下是本地知识库中检索到的相关历史报错及其解决方案(按相关度降序)。",
        "请参考这些真实案例来增强回答,但不要逐字照搬;若与用户问题无关或不确定,请忽略。",
        "以上内容仅供参考,请以你自己的判断为准。",
    ]
    # 把提示头/尾插到案例列表前后
    body = "\n\n".join(_format_hit(i, h) for i, h in enumerate(top, 1))
    return lines[0] + "\n" + lines[1] + "\n\n" + body + "\n\n" + lines[2]


# ---------- 从代码提取检索信号(自动修复 /api/fix 用) ----------

# 异常类名:TypeError / ValueError / KeyError / ModuleNotFoundError ...
_ERROR_NAME_RE = re.compile(r"\b[A-Z][A-Za-z]*(?:Error|Exception|Warning|Fault)\b")

# import 语句:import requests / import numpy as np / from os import path
_IMPORT_RE = re.compile(
    r"^\s*(?:from\s+([A-Za-z_][A-Za-z0-9_.]*)|import\s+([A-Za-z_][A-Za-z0-9_.]*))",
    re.MULTILINE,
)


def extract_search_signals(code: str) -> str:
    """从代码里提取检索强信号(异常名 + import 的模块名),拼成检索词。

    用于自动修复(/api/fix):拿整段代码去搜知识库时信号会被变量名/逻辑稀释,
    先抠出 TypeError、requests 这类强关键词再搜,命中更准,且不额外调 AI。
    返回空格分隔的信号串;没有信号则返回空串。
    """
    if not (code or "").strip():
        return ""
    errors = _ERROR_NAME_RE.findall(code)
    imports = [m for pair in _IMPORT_RE.findall(code) for m in pair if m]
    signals: list[str] = []
    seen: set[str] = set()
    for s in [*errors, *imports]:
        if s not in seen:
            signals.append(s)
            seen.add(s)
    return " ".join(signals)
