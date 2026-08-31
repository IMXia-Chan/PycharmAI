"""检索内核:倒排索引 + BM25 打分 + 落盘复用 + 增量更新 + 高亮。

纯标准库实现(倒排表、BM25 公式、布尔解析、高亮都是手写的),只依赖
`core.analyzer.tokenize` 做分词。索引用 pickle 落盘到 data/index/,重启免重建;
写操作(增/删/改)后同步更新内存索引并落盘,保证索引与数据一致。

对外:
    - get_public_index(db) / get_private_index(db)  模块级单例(惰性加载)
    - SearchIndex.upsert / remove / rebuild / search
    - SearchHit dataclass(score + record + highlights)
"""
from __future__ import annotations

import hashlib
import html
import math
import pickle
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional, Union

from core.analyzer import PRIVATE_FIELDS, PUBLIC_FIELDS, tokenize
from core.models import PrivateRecord, PublicRecord

# BM25 参数(标准取值)
K1 = 1.5
B = 0.75

INDEX_DIR = Path(__file__).resolve().parent.parent / "data" / "index"


@dataclass
class SearchHit:
    """一条命中结果:相关度分数 + 原始记录 + 命中字段的高亮片段。"""

    score: float
    record: Union[PublicRecord, PrivateRecord]
    highlights: dict[str, str] = field(default_factory=dict)


def parse_query(query: str) -> tuple[list[str], list[str], list[str]]:
    """把用户输入解析成 (should, must, must_not) 三组词。

    规则:默认词间 OR(任一命中);`+词`/`AND` 必须命中;`-词`/`NOT` 排除。
    """
    should: list[str] = []
    must: list[str] = []
    must_not: list[str] = []
    mode = "should"  # should | must | not
    for raw in (query or "").split():
        up = raw.upper()
        if up == "AND":
            mode = "must"
            continue
        if up == "OR":
            mode = "should"
            continue
        if up == "NOT":
            mode = "not"
            continue
        if raw.startswith("+"):
            must.extend(tokenize(raw[1:]))
            continue
        if raw.startswith("-"):
            must_not.extend(tokenize(raw[1:]))
            continue
        if mode == "must":
            must.extend(tokenize(raw))
        elif mode == "not":
            must_not.extend(tokenize(raw))
        else:
            should.extend(tokenize(raw))
    return should, must, must_not


class SearchIndex:
    """单个库的检索索引(倒排 + BM25)。"""

    def __init__(self, name: str, fields: dict[str, float], kind: str):
        self.name = name                      # "public" | "private"
        self.fields = fields                  # 字段 -> boost
        self.kind = kind
        self.path = INDEX_DIR / f"{name}.pkl"
        # term -> {doc_id -> {field -> [positions]}}
        self.postings: dict[str, dict[str, dict[str, list[int]]]] = {}
        self.doc_lengths: dict[str, int] = {}  # doc_id -> 总词数
        self.docs: dict[str, dict] = {}        # doc_id -> 原始记录 dict(用于返回)
        self._avgdl = 0.0

    # ---------- 字段 / 文档标识 ----------

    def _fields_of(self, record) -> dict[str, str]:
        if self.kind == "private":
            return {
                "error_type": record.error_type or "",
                "error_message": record.error_message or "",
                "solution": record.solution or "",
                "code_context": record.code_context or "",
                "file_path": record.file_path or "",
                "language": record.language or "",
            }
        return {
            "error_type": record.error_type or "",
            "error_message": record.error_message or "",
            "solution": record.solution or "",
            "tags": " ".join(record.tags or []),
            "language": record.language or "",
            "source": record.source or "",
        }

    def _doc_id(self, record) -> str:
        if self.kind == "private":
            return getattr(record, "id", "")
        key = f"{record.error_type}\x00{record.error_message}\x00{record.source}"
        return hashlib.md5(key.encode("utf-8")).hexdigest()

    # ---------- 构建 / 落盘 ----------

    def ensure_synced(self, db) -> None:
        """首次加载:索引文件存在且记录数一致则直接复用,否则从 db 重建。"""
        records = db.all()
        if self.path.exists():
            try:
                self._load()
            except Exception:
                self.postings, self.doc_lengths, self.docs = {}, {}, {}
                self._avgdl = 0.0
            if len(self.docs) == len(records):
                return
        self.rebuild(records)

    def rebuild(self, records) -> None:
        self.postings = {}
        self.doc_lengths = {}
        self.docs = {}
        for r in records:
            self._index_record(r)
        self._recalc_avgdl()
        self._save()

    def _index_record(self, record) -> None:
        doc_id = self._doc_id(record)
        self.docs[doc_id] = asdict(record)
        total = 0
        for fname, text in self._fields_of(record).items():
            tokens = tokenize(text)
            total += len(tokens)
            for pos, term in enumerate(tokens):
                self.postings.setdefault(term, {}).setdefault(doc_id, {}).setdefault(fname, []).append(pos)
        self.doc_lengths[doc_id] = total

    def _remove_doc(self, doc_id: str) -> None:
        self.docs.pop(doc_id, None)
        self.doc_lengths.pop(doc_id, None)
        for term in list(self.postings):
            self.postings[term].pop(doc_id, None)
            if not self.postings[term]:
                del self.postings[term]

    def _recalc_avgdl(self) -> None:
        self._avgdl = sum(self.doc_lengths.values()) / max(1, len(self.doc_lengths))

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "postings": self.postings,
            "doc_lengths": self.doc_lengths,
            "docs": self.docs,
            "avgdl": self._avgdl,
        }
        with self.path.open("wb") as f:
            pickle.dump(data, f)

    def _load(self) -> None:
        with self.path.open("rb") as f:
            data = pickle.load(f)
        self.postings = data["postings"]
        self.doc_lengths = data["doc_lengths"]
        self.docs = data["docs"]
        self._avgdl = data["avgdl"]

    # ---------- 增量更新(写时索引) ----------

    def upsert(self, record) -> None:
        self._remove_doc(self._doc_id(record))
        self._index_record(record)
        self._recalc_avgdl()
        self._save()

    def upsert_many(self, records) -> None:
        """批量写入若干条记录,只落盘一次(供爬虫大量灌库,避免每条一次 pickle 的 O(n²))。

        逐个 `_remove_doc` + `_index_record` 累加进内存索引,最后统一
        `_recalc_avgdl` + `_save`。records 为空时不做任何事。
        """
        if not records:
            return
        for r in records:
            self._remove_doc(self._doc_id(r))
            self._index_record(r)
        self._recalc_avgdl()
        self._save()

    def remove(self, doc_id: str) -> None:
        self._remove_doc(doc_id)
        self._recalc_avgdl()
        self._save()

    # ---------- 查询 ----------

    def search(self, query: str, limit: int = 50) -> list[SearchHit]:
        should, must, must_not = parse_query(query)
        terms = should + must
        if not terms:
            return []
        candidates: set[str] = set()
        for t in terms:
            candidates.update(self.postings.get(t, {}).keys())
        if not candidates:
            return []
        n_docs = len(self.docs)
        avgdl = self._avgdl or 1.0

        scored: list[tuple[float, str]] = []
        for doc_id in candidates:
            if must and any(t not in self.postings or doc_id not in self.postings[t] for t in must):
                continue
            if must_not and any(t in self.postings and doc_id in self.postings[t] for t in must_not):
                continue
            score = 0.0
            for t in terms:
                post = self.postings.get(t, {})
                if doc_id not in post:
                    continue
                idf = math.log(1 + (n_docs - len(post) + 0.5) / (len(post) + 0.5))
                tf = sum(len(positions) * self.fields.get(f, 1.0) for f, positions in post[doc_id].items())
                dl = self.doc_lengths.get(doc_id, 0) or 0
                norm = tf * (K1 + 1) / (tf + K1 * (1 - B + B * dl / avgdl))
                score += idf * norm
            scored.append((score, doc_id))

        scored.sort(key=lambda x: -x[0])
        hits: list[SearchHit] = []
        for score, doc_id in scored[:limit]:
            record = self._record_from_dict(self.docs[doc_id])
            hits.append(SearchHit(score=score, record=record, highlights=self._highlight(record, terms)))
        return hits

    def _record_from_dict(self, d: dict):
        if self.kind == "private":
            return PrivateRecord.from_dict(d)
        return PublicRecord.from_dict(d)

    def _highlight(self, record, terms: list[str]) -> dict[str, str]:
        result: dict[str, str] = {}
        for fname, text in self._fields_of(record).items():
            if not text:
                continue
            escaped = html.escape(text)
            changed = False
            for t in terms:
                pattern = re.compile(re.escape(t) + r"(?![A-Za-z0-9_])", re.IGNORECASE)
                new = pattern.sub(lambda m: f"<mark>{m.group(0)}</mark>", escaped)
                if new != escaped:
                    changed = True
                    escaped = new
            if changed:
                result[fname] = escaped
        return result


# ---------- 模块级单例(跨实例共享,避免每次请求重载索引) ----------

_private_index: Optional[SearchIndex] = None
_public_index: Optional[SearchIndex] = None


def get_private_index(db=None) -> SearchIndex:
    global _private_index
    if _private_index is None:
        _private_index = SearchIndex("private", PRIVATE_FIELDS, "private")
        if db is not None:
            _private_index.ensure_synced(db)
    return _private_index


def get_public_index(db=None) -> SearchIndex:
    global _public_index
    if _public_index is None:
        _public_index = SearchIndex("public", PUBLIC_FIELDS, "public")
        if db is not None:
            _public_index.ensure_synced(db)
    return _public_index


def reload_public_index(db=None) -> SearchIndex:
    """强制重载公共库索引:丢弃内存单例,重新从磁盘读(或从数据重建)。

    灌库是在独立进程里跑的,后端进程一旦加载过索引就缓存进内存,
    调用本函数让后端立刻读到磁盘上的新数据,无需重启进程。
    """
    global _public_index
    _public_index = None
    return get_public_index(db)


def reload_private_index(db=None) -> SearchIndex:
    """强制重载个人库索引:丢弃内存单例,重新从磁盘读(或从数据重建)。"""
    global _private_index
    _private_index = None
    return get_private_index(db)
