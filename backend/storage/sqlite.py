"""本地 SQLite 存储(调试/无云端时兜底)。"""
from __future__ import annotations

import sqlite3
import threading
import uuid
from datetime import datetime

from .base import Storage


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class SqliteStorage(Storage):
    def __init__(self, path: str):
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init()

    def _init(self) -> None:
        with self._lock:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS records (
                    id TEXT PRIMARY KEY,
                    code TEXT, filename TEXT, line INTEGER,
                    category TEXT, title TEXT, message TEXT,
                    severity TEXT, ai_analysis TEXT, created_at TEXT
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS notes (
                    id TEXT PRIMARY KEY,
                    title TEXT, content TEXT, created_at TEXT
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS snippets (
                    id TEXT PRIMARY KEY,
                    title TEXT, code TEXT, note TEXT, created_at TEXT
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS libraries (
                    id TEXT PRIMARY KEY,
                    name TEXT, created_at TEXT
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS library_items (
                    id TEXT PRIMARY KEY,
                    library_id TEXT, kind TEXT, ref_id TEXT,
                    title TEXT, content TEXT, created_at TEXT
                )
                """
            )
            self._conn.commit()

    def add_record(self, record: dict, username: str = "", token: str = "") -> dict:
        record = dict(record)
        record["id"] = uuid.uuid4().hex
        record["created_at"] = _now()
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO records
                (id, code, filename, line, category, title, message, severity, ai_analysis, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    record["id"], record.get("code", ""), record.get("filename", ""),
                    record.get("line", 0), record.get("category", "unknown"),
                    record.get("title", ""), record.get("message", ""),
                    record.get("severity", "info"), record.get("ai_analysis", ""),
                    record["created_at"],
                ),
            )
            self._conn.commit()
        return record

    def list_records(self, limit: int = 50, username: str = "", token: str = "") -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM records ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def add_note(self, note: dict, username: str = "", token: str = "") -> dict:
        note = dict(note)
        note["id"] = uuid.uuid4().hex
        note["created_at"] = _now()
        with self._lock:
            self._conn.execute(
                "INSERT INTO notes (id, title, content, created_at) VALUES (?,?,?,?)",
                (note["id"], note.get("title", ""), note.get("content", ""), note["created_at"]),
            )
            self._conn.commit()
        return note

    def list_notes(self, limit: int = 20, username: str = "", token: str = "") -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM notes ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def add_snippet(self, snippet: dict, username: str = "", token: str = "") -> dict:
        snippet = dict(snippet)
        snippet["id"] = uuid.uuid4().hex
        snippet["created_at"] = _now()
        with self._lock:
            self._conn.execute(
                "INSERT INTO snippets (id, title, code, note, created_at) VALUES (?,?,?,?,?)",
                (snippet["id"], snippet.get("title", ""), snippet.get("code", ""),
                 snippet.get("note", ""), snippet["created_at"]),
            )
            self._conn.commit()
        return snippet

    def list_snippets(self, limit: int = 100, username: str = "", token: str = "") -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM snippets ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def delete_snippet(self, snippet_id: str, username: str = "", token: str = "") -> bool:
        with self._lock:
            cur = self._conn.execute("DELETE FROM snippets WHERE id = ?", (snippet_id,))
            self._conn.commit()
        return cur.rowcount > 0

    def delete_note(self, note_id: str, username: str = "", token: str = "") -> bool:
        with self._lock:
            cur = self._conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
            self._conn.commit()
        return cur.rowcount > 0

    def delete_record(self, record_id: str, username: str = "", token: str = "") -> bool:
        with self._lock:
            cur = self._conn.execute("DELETE FROM records WHERE id = ?", (record_id,))
            self._conn.commit()
        return cur.rowcount > 0

    def add_library(self, library: dict, username: str = "", token: str = "") -> dict:
        library = dict(library)
        library["id"] = uuid.uuid4().hex
        library["created_at"] = _now()
        with self._lock:
            self._conn.execute(
                "INSERT INTO libraries (id, name, created_at) VALUES (?,?,?)",
                (library["id"], library.get("name", ""), library["created_at"]),
            )
            self._conn.commit()
        return library

    def list_libraries(self, username: str = "", token: str = "") -> list[dict]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM libraries ORDER BY created_at ASC").fetchall()
            items = self._conn.execute("SELECT * FROM library_items ORDER BY created_at ASC").fetchall()
        libs = [dict(r) for r in rows]
        by_lib: dict[str, list[dict]] = {}
        for it in items:
            it = dict(it)
            by_lib.setdefault(it.get("library_id", ""), []).append(it)
        for lib in libs:
            lib["items"] = by_lib.get(lib["id"], [])
        return libs

    def delete_library(self, library_id: str, username: str = "", token: str = "") -> bool:
        with self._lock:
            self._conn.execute("DELETE FROM library_items WHERE library_id = ?", (library_id,))
            cur = self._conn.execute("DELETE FROM libraries WHERE id = ?", (library_id,))
            self._conn.commit()
        return cur.rowcount > 0

    def add_library_item(self, library_id: str, item: dict, username: str = "", token: str = "") -> dict:
        item = dict(item)
        item["id"] = uuid.uuid4().hex
        item["library_id"] = library_id
        item["created_at"] = _now()
        with self._lock:
            self._conn.execute(
                "INSERT INTO library_items (id, library_id, kind, ref_id, title, content, created_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (
                    item["id"], library_id, item.get("kind", "note"), item.get("ref_id", ""),
                    item.get("title", ""), item.get("content", ""), item["created_at"],
                ),
            )
            self._conn.commit()
        return item

    def delete_library_item(self, library_id: str, item_id: str, username: str = "", token: str = "") -> bool:
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM library_items WHERE id = ? AND library_id = ?", (item_id, library_id)
            )
            self._conn.commit()
        return cur.rowcount > 0
