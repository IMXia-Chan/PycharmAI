"""远程云端存储:把记录/笔记同步到 server/ 服务(真云端,多用户)。"""
from __future__ import annotations

import httpx

from .base import Storage


class RemoteStorage(Storage):
    def __init__(self, base_url: str, token: str, timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.token = token  # 兜底令牌;多用户模式下每请求传各自 token
        self.timeout = timeout

    def _headers(self, username: str, token: str) -> dict:
        return {
            "Authorization": f"Bearer {token or self.token}",
            "X-Username": username,
            "Content-Type": "application/json",
        }

    def add_record(self, record: dict, username: str = "", token: str = "") -> dict:
        with httpx.Client(timeout=self.timeout) as c:
            r = c.post(f"{self.base_url}/records", json=record, headers=self._headers(username, token))
            r.raise_for_status()
            return r.json()

    def list_records(self, limit: int = 50, username: str = "", token: str = "") -> list[dict]:
        with httpx.Client(timeout=self.timeout) as c:
            r = c.get(f"{self.base_url}/records", params={"limit": limit}, headers=self._headers(username, token))
            r.raise_for_status()
            return r.json()

    def add_note(self, note: dict, username: str = "", token: str = "") -> dict:
        with httpx.Client(timeout=self.timeout) as c:
            r = c.post(f"{self.base_url}/notes", json=note, headers=self._headers(username, token))
            r.raise_for_status()
            return r.json()

    def list_notes(self, limit: int = 20, username: str = "", token: str = "") -> list[dict]:
        with httpx.Client(timeout=self.timeout) as c:
            r = c.get(f"{self.base_url}/notes", params={"limit": limit}, headers=self._headers(username, token))
            r.raise_for_status()
            return r.json()

    def delete_note(self, note_id: str, username: str = "", token: str = "") -> bool:
        with httpx.Client(timeout=self.timeout) as c:
            r = c.delete(f"{self.base_url}/notes/{note_id}", headers=self._headers(username, token))
            r.raise_for_status()
            return r.json().get("ok", False)

    def delete_record(self, record_id: str, username: str = "", token: str = "") -> bool:
        with httpx.Client(timeout=self.timeout) as c:
            r = c.delete(f"{self.base_url}/records/{record_id}", headers=self._headers(username, token))
            r.raise_for_status()
            return r.json().get("ok", False)

    def add_snippet(self, snippet: dict, username: str = "", token: str = "") -> dict:
        with httpx.Client(timeout=self.timeout) as c:
            r = c.post(f"{self.base_url}/snippets", json=snippet, headers=self._headers(username, token))
            r.raise_for_status()
            return r.json()

    def list_snippets(self, limit: int = 100, username: str = "", token: str = "") -> list[dict]:
        with httpx.Client(timeout=self.timeout) as c:
            r = c.get(f"{self.base_url}/snippets", params={"limit": limit}, headers=self._headers(username, token))
            r.raise_for_status()
            return r.json()

    def delete_snippet(self, snippet_id: str, username: str = "", token: str = "") -> bool:
        with httpx.Client(timeout=self.timeout) as c:
            r = c.delete(f"{self.base_url}/snippets/{snippet_id}", headers=self._headers(username, token))
            r.raise_for_status()
            return r.json().get("ok", False)

    def add_library(self, library: dict, username: str = "", token: str = "") -> dict:
        with httpx.Client(timeout=self.timeout) as c:
            r = c.post(f"{self.base_url}/libraries", json=library, headers=self._headers(username, token))
            r.raise_for_status()
            return r.json()

    def list_libraries(self, username: str = "", token: str = "") -> list[dict]:
        with httpx.Client(timeout=self.timeout) as c:
            r = c.get(f"{self.base_url}/libraries", headers=self._headers(username, token))
            r.raise_for_status()
            return r.json()

    def delete_library(self, library_id: str, username: str = "", token: str = "") -> bool:
        with httpx.Client(timeout=self.timeout) as c:
            r = c.delete(f"{self.base_url}/libraries/{library_id}", headers=self._headers(username, token))
            r.raise_for_status()
            return r.json().get("ok", False)

    def add_library_item(self, library_id: str, item: dict, username: str = "", token: str = "") -> dict:
        with httpx.Client(timeout=self.timeout) as c:
            r = c.post(f"{self.base_url}/libraries/{library_id}/items", json=item, headers=self._headers(username, token))
            r.raise_for_status()
            return r.json()

    def delete_library_item(self, library_id: str, item_id: str, username: str = "", token: str = "") -> bool:
        with httpx.Client(timeout=self.timeout) as c:
            r = c.delete(f"{self.base_url}/libraries/{library_id}/items/{item_id}", headers=self._headers(username, token))
            r.raise_for_status()
            return r.json().get("ok", False)
