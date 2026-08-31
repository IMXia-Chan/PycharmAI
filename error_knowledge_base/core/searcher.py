"""检索入口:基于 indexer 的 BM25 关键词检索。

替代旧的暴力子串匹配,返回 SearchHit(score + record + highlights)。
"""
from __future__ import annotations

from core.indexer import SearchHit, get_private_index, get_public_index


class Searcher:
    """对外检索接口。构造时传 db(用于首次触发索引构建),内部用单例索引查询。"""

    def __init__(self, public_db, private_db):
        self.public_db = public_db
        self.private_db = private_db

    def search_public(self, keyword: str) -> list[SearchHit]:
        """搜公共库,返回按相关度降序的命中列表。"""
        return get_public_index(self.public_db).search(keyword)

    def search_private(self, keyword: str) -> list[SearchHit]:
        """搜个人库,返回按相关度降序的命中列表。"""
        return get_private_index(self.private_db).search(keyword)

    def search_all(self, keyword: str) -> dict[str, list[SearchHit]]:
        """同时在两个库搜索,返回 {"public": [...], "private": [...]}。"""
        return {
            "public": self.search_public(keyword),
            "private": self.search_private(keyword),
        }
