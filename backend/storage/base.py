"""存储抽象接口。"""
from __future__ import annotations

from abc import ABC, abstractmethod


class Storage(ABC):
    @abstractmethod
    def add_record(self, record: dict, username: str = "", token: str = "") -> dict:
        """保存一条不规范/错误代码记录,返回带 id 与 created_at 的记录。"""

    @abstractmethod
    def list_records(self, limit: int = 50, username: str = "", token: str = "") -> list[dict]:
        """按时间倒序返回记录列表。"""

    @abstractmethod
    def add_note(self, note: dict, username: str = "", token: str = "") -> dict:
        """保存一条 AI 生成的笔记。"""

    @abstractmethod
    def list_notes(self, limit: int = 20, username: str = "", token: str = "") -> list[dict]:
        """按时间倒序返回笔记列表。"""

    @abstractmethod
    def add_snippet(self, snippet: dict, username: str = "", token: str = "") -> dict:
        """保存一条代码片段。"""

    @abstractmethod
    def list_snippets(self, limit: int = 100, username: str = "", token: str = "") -> list[dict]:
        """按时间倒序返回代码片段列表。"""

    @abstractmethod
    def delete_snippet(self, snippet_id: str, username: str = "", token: str = "") -> bool:
        """删除一条代码片段,返回是否成功。"""

    @abstractmethod
    def delete_note(self, note_id: str, username: str = "", token: str = "") -> bool:
        """删除一条笔记,返回是否成功。"""

    @abstractmethod
    def delete_record(self, record_id: str, username: str = "", token: str = "") -> bool:
        """删除一条错误/不规范代码记录,返回是否成功。"""

    @abstractmethod
    def add_library(self, library: dict, username: str = "", token: str = "") -> dict:
        """创建一个文件库,返回带 id 与 created_at 的库。"""

    @abstractmethod
    def list_libraries(self, username: str = "", token: str = "") -> list[dict]:
        """返回文件库列表(每个库内含 items 列表)。"""

    @abstractmethod
    def delete_library(self, library_id: str, username: str = "", token: str = "") -> bool:
        """删除一个文件库(连同其条目),返回是否成功。"""

    @abstractmethod
    def add_library_item(self, library_id: str, item: dict, username: str = "", token: str = "") -> dict:
        """向文件库添加一条条目(笔记或文件),返回带 id 与 created_at 的条目。"""

    @abstractmethod
    def delete_library_item(self, library_id: str, item_id: str, username: str = "", token: str = "") -> bool:
        """从文件库删除一条条目,返回是否成功。"""
