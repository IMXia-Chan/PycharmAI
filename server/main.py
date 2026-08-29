"""云端文件库同步服务(真云端,多用户)。

每个用户用「用户名 + 令牌」标识,拥有独立的记录/笔记库。
首次使用某用户名即自动注册(内网轻量模式);之后令牌不符则拒绝。

部署:把本目录放到一台云服务器,`uvicorn main:app --host 0.0.0.0 --port 8001`。
然后在 backend/.env 设置 CLOUD_URL=http://<服务器IP>:8001。
插件侧填写自己的「用户名 + 令牌」即可。
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import uvicorn
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

DB_PATH = os.getenv("DB_PATH", "cloud.db")
PORT = int(os.getenv("PORT", "8001"))

app = FastAPI(title="代码助手云端文件库", version="2.0.0")

_lock = threading.Lock()
_conn = sqlite3.connect(DB_PATH, check_same_thread=False)
_conn.row_factory = sqlite3.Row


def _init() -> None:
    _conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            token TEXT NOT NULL
        )
        """
    )
    _conn.execute(
        """
        CREATE TABLE IF NOT EXISTS records (
            id TEXT PRIMARY KEY, username TEXT, code TEXT, filename TEXT, line INTEGER,
            category TEXT, title TEXT, message TEXT,
            severity TEXT, ai_analysis TEXT, created_at TEXT
        )
        """
    )
    _conn.execute(
        """
        CREATE TABLE IF NOT EXISTS notes (
            id TEXT PRIMARY KEY, username TEXT, title TEXT, content TEXT, created_at TEXT
        )
        """
    )
    _conn.execute(
        """
        CREATE TABLE IF NOT EXISTS snippets (
            id TEXT PRIMARY KEY, username TEXT, title TEXT, code TEXT, note TEXT, created_at TEXT
        )
        """
    )
    _conn.commit()
    # 旧库迁移:为已有的 records/notes 补 username 列
    for table in ("records", "notes"):
        cols = {r["name"] for r in _conn.execute(f"PRAGMA table_info({table})").fetchall()}
        if "username" not in cols:
            _conn.execute(f"ALTER TABLE {table} ADD COLUMN username TEXT")
            _conn.commit()


_init()


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _auth(username: str, token: str) -> str:
    """校验「用户名 + 令牌」;首次出现即注册。返回规范化后的用户名。"""
    username = (username or "").strip()
    token = (token or "").strip()
    if not username or not token:
        raise HTTPException(status_code=401, detail="缺少用户名或令牌")
    with _lock:
        row = _conn.execute("SELECT token FROM users WHERE username = ?", (username,)).fetchone()
        if row is None:
            _conn.execute("INSERT INTO users (username, token) VALUES (?,?)", (username, token))
            _conn.commit()
            return username
        if row["token"] != token:
            raise HTTPException(status_code=401, detail="用户名或令牌不正确")
    return username


def _identity(
    x_username: Optional[str] = Header(None, alias="X-Username"),
    authorization: Optional[str] = Header(None),
) -> str:
    token = ""
    if authorization and authorization.startswith("Bearer "):
        token = authorization[len("Bearer "):]
    return _auth(x_username or "", token)


@app.get("/health")
def health():
    return {"status": "ok"}


LATEST_JSON = BASE_DIR / "latest.json"


@app.get("/version")
def version():
    """返回插件最新版本信息(公开接口,无需鉴权)。发布新版本只需改 latest.json。"""
    try:
        data = json.loads(LATEST_JSON.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {"version": "", "message": "", "url": ""}
    return {
        "version": str(data.get("version", "")).strip(),
        "message": str(data.get("message", "")).strip(),
        "url": str(data.get("url", "")).strip(),
    }


@app.post("/records")
def add_record(body: dict, username: str = Depends(_identity)):
    body = dict(body)
    body["username"] = username
    body.setdefault("id", uuid.uuid4().hex)
    body.setdefault("created_at", _now())
    with _lock:
        _conn.execute(
            """
            INSERT OR REPLACE INTO records
            (id, username, code, filename, line, category, title, message, severity, ai_analysis, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                body["id"], username, body.get("code", ""), body.get("filename", ""),
                body.get("line", 0), body.get("category", "unknown"),
                body.get("title", ""), body.get("message", ""),
                body.get("severity", "info"), body.get("ai_analysis", ""),
                body["created_at"],
            ),
        )
        _conn.commit()
    return body


@app.get("/records")
def list_records(limit: int = 50, username: str = Depends(_identity)):
    with _lock:
        rows = _conn.execute(
            "SELECT * FROM records WHERE username = ? ORDER BY created_at DESC LIMIT ?",
            (username, limit),
        ).fetchall()
    return [dict(r) for r in rows]


@app.delete("/records/{record_id}")
def delete_record(record_id: str, username: str = Depends(_identity)):
    with _lock:
        cur = _conn.execute(
            "DELETE FROM records WHERE id = ? AND username = ?", (record_id, username)
        )
        _conn.commit()
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="记录不存在")
    return {"ok": True}


@app.post("/notes")
def add_note(body: dict, username: str = Depends(_identity)):
    body = dict(body)
    body["username"] = username
    body.setdefault("id", uuid.uuid4().hex)
    body.setdefault("created_at", _now())
    with _lock:
        _conn.execute(
            "INSERT INTO notes (id, username, title, content, created_at) VALUES (?,?,?,?,?)",
            (body["id"], username, body.get("title", ""), body.get("content", ""), body["created_at"]),
        )
        _conn.commit()
    return body


@app.get("/notes")
def list_notes(limit: int = 20, username: str = Depends(_identity)):
    with _lock:
        rows = _conn.execute(
            "SELECT * FROM notes WHERE username = ? ORDER BY created_at DESC LIMIT ?",
            (username, limit),
        ).fetchall()
    return [dict(r) for r in rows]


@app.post("/snippets")
def add_snippet(body: dict, username: str = Depends(_identity)):
    body = dict(body)
    body["username"] = username
    body.setdefault("id", uuid.uuid4().hex)
    body.setdefault("created_at", _now())
    with _lock:
        _conn.execute(
            "INSERT INTO snippets (id, username, title, code, note, created_at) VALUES (?,?,?,?,?,?)",
            (body["id"], username, body.get("title", ""), body.get("code", ""),
             body.get("note", ""), body["created_at"]),
        )
        _conn.commit()
    return body


@app.get("/snippets")
def list_snippets(limit: int = 100, username: str = Depends(_identity)):
    with _lock:
        rows = _conn.execute(
            "SELECT * FROM snippets WHERE username = ? ORDER BY created_at DESC LIMIT ?",
            (username, limit),
        ).fetchall()
    return [dict(r) for r in rows]


@app.delete("/snippets/{snippet_id}")
def delete_snippet(snippet_id: str, username: str = Depends(_identity)):
    with _lock:
        cur = _conn.execute(
            "DELETE FROM snippets WHERE id = ? AND username = ?", (snippet_id, username)
        )
        _conn.commit()
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="片段不存在")
    return {"ok": True}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=PORT)
