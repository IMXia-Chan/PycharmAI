"""云端文件库同步服务(真云端,多用户)。

每个用户用「用户名 + 令牌」标识,拥有独立的记录/笔记库。
首次使用某用户名即自动注册(内网轻量模式);之后令牌不符则拒绝。

部署:把本目录放到一台云服务器,`uvicorn main:app --host 0.0.0.0 --port 8001`。
然后在 backend/.env 设置 CLOUD_URL=http://<服务器IP>:8001。
插件侧填写自己的「用户名 + 令牌」即可。
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import smtplib
import sqlite3
import threading
import time
import uuid
from datetime import datetime
from email.header import Header as EmailHeader
from email.mime.text import MIMEText
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


# ---------- 管理员登录(2FA:用户名 + 密码 + 邮箱验证码) ----------

CLOUD_TOKEN = os.getenv("CLOUD_TOKEN", "dev-token")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "")
ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH", "")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.qq.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")

_admin_lock = threading.Lock()
_pending_codes: dict[str, dict] = {}      # ticket -> {code, expires_at, attempts}
_sessions: dict[str, float] = {}          # session_token -> expires_at
_login_fails: dict[str, list[float]] = {}  # 用户名 -> 失败时间戳列表


def _hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode("utf-8")).hexdigest()


def _mask_email(email: str) -> str:
    if "@" not in email:
        return (email[:1] + "***") if email else "***"
    name, domain = email.split("@", 1)
    return (name[:1] + "***@" + domain) if name else "***@" + domain


def _send_code(to_addr: str, code: str) -> None:
    msg = MIMEText(f"你的管理员登录验证码是:{code},5 分钟内有效。", "plain", "utf-8")
    msg["Subject"] = EmailHeader("代码助手 - 管理员登录验证码", "utf-8")
    msg["From"] = SMTP_USER
    msg["To"] = to_addr
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=15) as s:
        s.login(SMTP_USER, SMTP_PASSWORD)
        s.sendmail(SMTP_USER, [to_addr], msg.as_string())


def _admin_key(x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key")) -> str:
    """后端↔云端之间的服务间密钥:防止陌生人直连服务器打管理员接口。"""
    if x_admin_key != CLOUD_TOKEN:
        raise HTTPException(status_code=403, detail="无管理员接口访问权限")
    return ""


@app.post("/admin/login")
def admin_login(body: dict, _: str = Depends(_admin_key)):
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""
    if not ADMIN_USERNAME or not ADMIN_PASSWORD_HASH or not ADMIN_EMAIL:
        return {"ok": False, "error": "服务器未配置管理员账号(缺 server/.env 配置)"}

    now = time.time()
    # 限速:同一用户名 5 分钟内失败超过 5 次则拒绝
    with _admin_lock:
        fails = [t for t in _login_fails.get(username, []) if now - t < 300]
        _login_fails[username] = fails
        if len(fails) >= 5:
            raise HTTPException(status_code=429, detail="尝试次数过多,请 5 分钟后再试")

    if username != ADMIN_USERNAME or _hash_password(password) != ADMIN_PASSWORD_HASH:
        with _admin_lock:
            _login_fails.setdefault(username, []).append(now)
        raise HTTPException(status_code=401, detail="管理员用户名或密码错误")

    code = f"{secrets.randbelow(1000000):06d}"
    ticket = secrets.token_hex(16)
    with _admin_lock:
        _pending_codes[ticket] = {"code": code, "expires_at": now + 300, "attempts": 0}
        _login_fails.pop(username, None)  # 登录成功,清空失败计数
    try:
        _send_code(ADMIN_EMAIL, code)
    except Exception as e:  # noqa: BLE001
        with _admin_lock:
            _pending_codes.pop(ticket, None)
        raise HTTPException(status_code=500, detail=f"验证码发送失败:{e}")
    return {"ok": True, "ticket": ticket, "email": _mask_email(ADMIN_EMAIL)}


@app.post("/admin/verify")
def admin_verify(body: dict, _: str = Depends(_admin_key)):
    ticket = (body.get("ticket") or "").strip()
    code = (body.get("code") or "").strip()
    with _admin_lock:
        rec = _pending_codes.get(ticket)
        if rec is None:
            raise HTTPException(status_code=400, detail="验证码已过期,请重新发送")
        if rec["expires_at"] < time.time():
            del _pending_codes[ticket]
            raise HTTPException(status_code=400, detail="验证码已过期,请重新发送")
        rec["attempts"] += 1
        if rec["attempts"] > 5:
            del _pending_codes[ticket]
            raise HTTPException(status_code=400, detail="尝试次数过多,请重新发送")
        if rec["code"] != code:
            raise HTTPException(status_code=400, detail="验证码错误")
        del _pending_codes[ticket]
        token = secrets.token_hex(32)
        _sessions[token] = time.time() + 12 * 3600
    return {"ok": True, "session_token": token}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=PORT)
