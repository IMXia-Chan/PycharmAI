"""知识库 API:对接 ErrorKnowledgeBase(纯本地双库知识库系统)。

- 公共库:只读,只能由爬虫写入(这里只暴露查询);
- 个人库:增删改查;
- 数据在 D:\\ai-code-assistant\\error_knowledge_base\\data\\,独立于后端 SQLite。
"""
from __future__ import annotations

import sys
from dataclasses import asdict
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from .models import KbPrivateIn, KbPrivateOut, KbPublicOut, KbSearchHitPrivate, KbSearchHitPublic

# 复用 error_knowledge_base 的 core(数据模型 / 存储 / 检索)
_KB_DIR = Path(__file__).resolve().parent.parent / "error_knowledge_base"
if str(_KB_DIR) not in sys.path:
    sys.path.insert(0, str(_KB_DIR))

from core.indexer import reload_private_index, reload_public_index  # noqa: E402
from core.models import PrivateRecord  # noqa: E402
from core.searcher import Searcher  # noqa: E402
from core.storage import PrivateDatabase, PublicDatabase  # noqa: E402

router = APIRouter(prefix="/api/kb", tags=["知识库"])


# ---------- 公共库(只读) ----------

@router.get("/public", response_model=list[KbPublicOut])
def list_public() -> list[dict]:
    """列出公共库全部记录(只读,来自 GitHub 爬取)。"""
    return [asdict(r) for r in PublicDatabase().all()]


@router.get("/public/search", response_model=list[KbSearchHitPublic])
def search_public(q: str = Query("", description="关键词")) -> list[dict]:
    """按关键词搜公共库(返回相关度分数 + 命中高亮 + 记录)。"""
    hits = Searcher(PublicDatabase(), PrivateDatabase()).search_public(q)
    return [{"score": h.score, "highlights": h.highlights, "record": asdict(h.record)} for h in hits]


# ---------- 个人库(增删改查) ----------

@router.get("/private", response_model=list[KbPrivateOut])
def list_private() -> list[dict]:
    """列出个人库全部记录。"""
    return [asdict(r) for r in PrivateDatabase().all()]


@router.post("/private", response_model=KbPrivateOut)
def add_private(body: KbPrivateIn) -> dict:
    """新增一条个人报错记录。"""
    rec = PrivateRecord(
        error_type=body.error_type,
        error_message=body.error_message,
        language=body.language,
        solution=body.solution,
        code_context=body.code_context,
        file_path=body.file_path,
        solution_verified=body.solution_verified,
    )
    return asdict(PrivateDatabase().add(rec))


@router.get("/private/search", response_model=list[KbSearchHitPrivate])
def search_private(q: str = Query("", description="关键词")) -> list[dict]:
    """按关键词搜个人库(返回相关度分数 + 命中高亮 + 记录)。"""
    hits = Searcher(PublicDatabase(), PrivateDatabase()).search_private(q)
    return [{"score": h.score, "highlights": h.highlights, "record": asdict(h.record)} for h in hits]


@router.get("/private/{record_id}", response_model=KbPrivateOut)
def get_private(record_id: str) -> dict:
    """按 id 查一条个人记录。"""
    rec = PrivateDatabase().get(record_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="记录不存在")
    return asdict(rec)


@router.put("/private/{record_id}", response_model=KbPrivateOut)
def update_private(record_id: str, body: KbPrivateIn) -> dict:
    """按 id 修改一条个人记录(只更新传入的字段)。"""
    changes = body.model_dump(exclude_unset=True)
    rec = PrivateDatabase().update(record_id, **changes)
    if rec is None:
        raise HTTPException(status_code=404, detail="记录不存在")
    return asdict(rec)


@router.delete("/private/{record_id}")
def delete_private(record_id: str) -> dict:
    """按 id 删除一条个人记录。"""
    if not PrivateDatabase().delete(record_id):
        raise HTTPException(status_code=404, detail="记录不存在")
    return {"ok": True}


# ---------- 综合搜索 ----------

@router.get("/search")
def search_all(q: str = Query("", description="关键词")) -> dict[str, list]:
    """同时在两个库搜索,返回 {"public": [...], "private": [...]}(每项含 score/highlights/record)。"""
    result = Searcher(PublicDatabase(), PrivateDatabase()).search_all(q)
    return {
        "public": [{"score": h.score, "highlights": h.highlights, "record": asdict(h.record)} for h in result["public"]],
        "private": [{"score": h.score, "highlights": h.highlights, "record": asdict(h.record)} for h in result["private"]],
    }


# ---------- 重载索引 ----------

@router.post("/reload")
def reload_index() -> dict:
    """强制重载检索索引:丢弃后端进程里的内存缓存,从磁盘重新加载。

    灌库(fill_public)是在独立进程里跑的,后端一旦加载过索引就缓存进内存,
    不会感知磁盘数据变化。灌完库点一下本接口,后端立刻读到新数据,无需重启。
    """
    pub_db = PublicDatabase()
    priv_db = PrivateDatabase()
    reload_public_index(pub_db)
    reload_private_index(priv_db)
    # 向量索引(中文检索语义兜底)也一并重建;fastembed 未安装时跳过,不影响主流程
    try:
        from core.vector import reload_public_vector
        reload_public_vector(pub_db)
    except ImportError:
        pass
    return {"ok": True, "public": pub_db.count(), "private": priv_db.count()}
