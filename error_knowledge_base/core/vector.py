"""本地多语言向量检索:让中文查询也能命中英文知识库。

用 fastembed(基于 ONNX Runtime,不引入 PyTorch)加载多语言嵌入模型
(默认 intfloat/multilingual-e5-large),把公共库每条记录编码成向量落盘复用,查询时把
中/英文查询也编码成同空间向量,按余弦相似度召回。

这是对 BM25 的补充:BM25 是关键词精确匹配,中文词在英文索引里永远
匹配不到,所以中文查询会零命中;向量是跨语言语义匹配,「类型错误」
和 TypeError 在向量空间里距离很近,能正常召回。

设计要点:
    - 模型与依赖全部懒加载;fastembed/numpy 未安装时,检索自动回退到
      BM25,不会让后端崩溃(searcher 里做了 ImportError 兜底);
    - 向量只给公共库建(个人库是中文,BM25 用 jieba 已能匹配);
    - 索引用 pickle 落盘 data/index/{name}_vec.pkl,重启免重算;
    - 记录数与数据不一致时自动重建(与 indexer 的 ensure_synced 同思路)。

用法:
    python -m core.vector           # 一次性构建公共库向量索引
"""
from __future__ import annotations

import hashlib
import os
import pickle
from pathlib import Path
from typing import Optional

import numpy as np

# HuggingFace 官方源在国内经常连不上,默认走国内镜像 hf-mirror;
# 海外或有代理可设 HF_ENDPOINT 覆盖(需在首次下载模型前设置)。
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
# hf-mirror 不支持 HF 的 Xet 存储后端(会报 401),关闭 Xet 改走普通 HTTP 下载。
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

INDEX_DIR = Path(__file__).resolve().parent.parent / "data" / "index"

# 多语言嵌入模型(fastembed 支持,均可换):
#   sentence-transformers/paraphrase-multilingual-mpnet-base-v2  768 维,50+ 语言,快准平衡(无需前缀,默认)
#   intfloat/multilingual-e5-large                      1024 维,94 语言,跨语言最强,但纯 CPU 慢(需 query/passage 前缀)
#   sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2  384 维,更小更快,无需前缀,精度低
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"

# e5 系列要求查询/文档分别加 "query: "/"passage: " 前缀;MiniLM / mpnet 无需,留空
QUERY_PREFIX = ""
PASSAGE_PREFIX = ""

# 相似度下限:低于此值的命中视为无关,丢弃(避免中文乱搜返回一堆英文噪声)
# MiniLM 跨语言正确匹配实测约 0.35~0.66,无关项 <0.2,取 0.25 留出召回余量
MIN_SCORE = 0.25

# 每条记录编码时拼接的字段,截断到 MAX_TEXT 字符,控制向量计算量与内存
MAX_TEXT = 1000

_embedder = None


def _vector_available() -> bool:
    """fastembed 是否可用(未安装则返回 False,检索回退 BM25)。"""
    try:
        import fastembed  # noqa: F401
        return True
    except ImportError:
        return False


def _get_embedder():
    """懒加载 fastembed 模型(单例)。首次调用会联网把模型下载到本机缓存。"""
    global _embedder
    if _embedder is None:
        from fastembed import TextEmbedding
        _embedder = TextEmbedding(model_name=MODEL_NAME)
    return _embedder


def _normalize(m: np.ndarray) -> np.ndarray:
    """按行 L2 归一化,使矩阵乘法等于余弦相似度;零向量保持不变。"""
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return m / norms


def _embed_batched(embedder, texts: list[str], batch: int = 128) -> list[np.ndarray]:
    """分批编码并打印进度,避免一次性把全部向量堆在内存里。

    批量越大越快,但 e5 的注意力矩阵随 batch 平方增长,内存峰值也随 batch 上涨;
    e5-large 下 batch=128 峰值约 6GB,易触发换页假死;mpnet/MiniLM 模型小得多,
    128 峰值仅 2~3GB,安全且更快,故默认 128(必要时对 e5-large 降到 64)。
    """
    out: list[np.ndarray] = []
    total = len(texts)
    for i in range(0, total, batch):
        chunk = texts[i:i + batch]
        out.extend(list(embedder.embed(chunk)))
        done = min(i + batch, total)
        print(f"    [向量] 编码进度 {done}/{total}", flush=True)
    return out


def _is_quality(record) -> bool:
    """判定一条记录是否值得入库(过滤爬虫误收的短噪声)。

    公共库爬虫会误收大量无意义短文本(如 LaTeX 宏定义),其 error_message 不足
    30 字符且 error_type 为空。这些记录编码后的向量语义空洞,却能与单个概念词
    (字典键/连接超时等)撞出 0.5 的相似度,污染短查询;而 MIN_SCORE 又无法把它们
    与正确命中(0.45~0.62)分开,所以干脆在编码前过滤掉。
    """
    return len(record.error_message or "") >= 30 or bool(record.error_type)


def _doc_id(record) -> str:
    """与 indexer.SearchIndex 一致的公共库文档标识(类型 + 信息 + 来源)。"""
    key = f"{record.error_type}\x00{record.error_message}\x00{record.source}"
    return hashlib.md5(key.encode("utf-8")).hexdigest()


class VectorIndex:
    """单个库的向量索引:doc_id + 归一化向量矩阵 + 原始记录 dict。"""

    def __init__(self, name: str):
        self.name = name
        self.path = INDEX_DIR / f"{name}_vec.pkl"
        self.doc_ids: list[str] = []
        self.matrix: Optional[np.ndarray] = None   # (n, dim) float32,已归一化
        self.records: list[dict] = []

    # ---------- 文档文本 ----------

    @staticmethod
    def _doc_text(record) -> str:
        parts = [
            record.error_type or "",
            record.error_message or "",
            record.solution or "",
            " ".join(record.tags or []),
        ]
        text = " ".join(p for p in parts if p)
        return PASSAGE_PREFIX + text[:MAX_TEXT]

    # ---------- 构建 / 落盘 ----------

    def ensure_synced(self, db) -> None:
        """首次加载:索引文件存在且记录数一致则直接复用,否则重建。"""
        records = [r for r in db.all() if _is_quality(r)]
        if self.path.exists():
            try:
                self._load()
            except Exception:
                self.doc_ids, self.matrix, self.records = [], None, []
            if len(self.records) == len(records):
                return
        self.rebuild(records)

    def rebuild(self, records) -> None:
        from dataclasses import asdict
        records = [r for r in records if _is_quality(r)]
        if not records:
            self.doc_ids, self.matrix, self.records = [], None, []
            return
        print(f"[向量] 开始为 {len(records)} 条记录编码(模型 {MODEL_NAME},首次运行会下载模型)…", flush=True)
        texts = [self._doc_text(r) for r in records]
        vecs = _embed_batched(_get_embedder(), texts)
        self.doc_ids = [_doc_id(r) for r in records]
        self.matrix = _normalize(np.asarray(vecs, dtype=np.float32))
        self.records = [asdict(r) for r in records]
        self._save()
        print(f"[向量] 完成,索引已落盘 {self.path}", flush=True)

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("wb") as f:
            pickle.dump({
                "model": MODEL_NAME,
                "doc_ids": self.doc_ids,
                "matrix": self.matrix,
                "records": self.records,
            }, f)

    def _load(self) -> None:
        with self.path.open("rb") as f:
            data = pickle.load(f)
        # 换了模型后,旧向量的维度/语义都不同,必须重建(抛异常让 ensure_synced 重建)
        if data.get("model") != MODEL_NAME:
            raise ValueError(f"向量索引模型不一致(磁盘 {data.get('model')!r} vs 当前 {MODEL_NAME!r}),需重建")
        self.doc_ids = data["doc_ids"]
        self.matrix = data["matrix"]
        self.records = data["records"]

    # ---------- 查询 ----------

    def search(self, query: str, top_k: int = 50) -> list[tuple[float, dict]]:
        """按语义相似度返回 [(score, record_dict), ...],降序,低于阈值已过滤。"""
        if self.matrix is None or not len(self.matrix) or not (query or "").strip():
            return []
        qv = _normalize(np.asarray(list(_get_embedder().embed([QUERY_PREFIX + query])), dtype=np.float32))
        scores = (self.matrix @ qv.T)[:, 0]
        order = np.argsort(-scores)[:top_k]
        hits: list[tuple[float, dict]] = []
        for i in order:
            s = float(scores[i])
            if s < MIN_SCORE:
                break  # 已按降序,后面的只会更低
            hits.append((s, self.records[i]))
        return hits


# ---------- 模块级单例(跨实例共享,避免每次请求重载索引) ----------

_public_vector: Optional[VectorIndex] = None


def get_public_vector(db=None) -> Optional[VectorIndex]:
    """公共库向量索引单例;fastembed 不可用时返回 None(检索回退 BM25)。"""
    global _public_vector
    if not _vector_available():
        return None
    if _public_vector is None:
        _public_vector = VectorIndex("public")
        if db is not None:
            _public_vector.ensure_synced(db)
    return _public_vector


def reload_public_vector(db=None) -> Optional[VectorIndex]:
    """强制重建公共库向量索引(灌库后调用,让后端立刻读到新数据,无需重启)。"""
    global _public_vector
    if not _vector_available():
        return None
    _public_vector = VectorIndex("public")
    if db is not None:
        _public_vector.ensure_synced(db)
    return _public_vector


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from core.storage import PublicDatabase  # noqa: E402
    db = PublicDatabase()
    print(f"公共库 {db.count()} 条记录")
    if not _vector_available():
        print("未安装 fastembed,退出。可执行: pip install fastembed")
        raise SystemExit(1)
    reload_public_vector(db)
    print("OK")
