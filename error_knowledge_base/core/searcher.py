"""检索入口:BM25 关键词检索 + 跨语言向量语义兜底。

公共库正文是英文(Stack Overflow),中文查询在 BM25 里零命中;当 BM25
无结果时,自动回退到 core.vector 的多语言向量检索,把「类型错误」这类
中文语义匹配到 TypeError 等英文记录。个人库是中文,BM25 用 jieba 已能
匹配,不参与向量兜底。
"""
from __future__ import annotations

from core.indexer import SearchHit, get_private_index, get_public_index
from core.models import PublicRecord


class Searcher:
    """对外检索接口。构造时传 db(用于首次触发索引构建),内部用单例索引查询。"""

    def __init__(self, public_db, private_db):
        self.public_db = public_db
        self.private_db = private_db

    def search_public(self, keyword: str) -> list[SearchHit]:
        """搜公共库,返回按相关度降序的命中列表。

        先走 BM25 关键词精确匹配;无命中时(中文查询几乎必为空,或英文拼写错误)
        回退到多语言向量语义检索。fastembed 未安装时向量层不可用,直接返回空。
        """
        hits = get_public_index(self.public_db).search(keyword)
        if hits or not (keyword or "").strip():
            return hits
        try:
            from core.vector import get_public_vector
        except ImportError:
            return []  # 未装 fastembed/numpy:回退,当作无命中
        vec = get_public_vector(self.public_db)
        if vec is None:
            return []
        return [
            SearchHit(score=score, record=PublicRecord.from_dict(d), highlights={})
            for score, d in vec.search(keyword)
        ]

    def search_private(self, keyword: str) -> list[SearchHit]:
        """搜个人库,返回按相关度降序的命中列表。"""
        return get_private_index(self.private_db).search(keyword)

    def search_all(self, keyword: str) -> dict[str, list[SearchHit]]:
        """同时在两个库搜索,返回 {"public": [...], "private": [...]}。"""
        return {
            "public": self.search_public(keyword),
            "private": self.search_private(keyword),
        }
