from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from pathlib import Path

from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "set_weaver.db"

_DEFAULT_USER = os.getenv("SET_WEAVER_ADMIN_USER", "setweaver")
_DEFAULT_PASSWORD = os.getenv("SET_WEAVER_ADMIN_PASSWORD", "setweaver123")


def _connect_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = _connect_db()
    with conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations_threads (
                thread_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id INTEGER NOT NULL,
                sender TEXT NOT NULL CHECK(sender IN ('user','assistant')),
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                FOREIGN KEY(thread_id) REFERENCES conversations_threads(thread_id)
            )
            """
        )
    conn.close()
    _ensure_default_user()


def _ensure_default_user() -> None:
    if find_user_by_username(_DEFAULT_USER):
        return
    create_user(_DEFAULT_USER, _DEFAULT_PASSWORD)


def create_user(username: str, password: str) -> sqlite3.Row | None:
    now = datetime.utcnow().isoformat()
    password_hash = generate_password_hash(password)
    conn = _connect_db()
    with conn:
        cursor = conn.execute(
            "INSERT OR IGNORE INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
            (username, password_hash, now),
        )
        if cursor.rowcount == 0:
            conn.close()
            return None
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return user


def find_user_by_username(username: str) -> sqlite3.Row | None:
    conn = _connect_db()
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return row


def verify_user(username: str, password: str) -> sqlite3.Row | None:
    user = find_user_by_username(username)
    if not user:
        return None
    if not check_password_hash(user["password_hash"], password):
        return None
    return user


def get_user_by_id(user_id: int) -> sqlite3.Row | None:
    conn = _connect_db()
    row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return row


def _thread_row_to_dict(row: sqlite3.Row) -> dict:
    return {
        "thread_id": row["thread_id"],
        "title": row["title"],
        "created_at": row["created_at"],
    }


def get_threads_for_user(user_id: int) -> list[dict]:
    conn = _connect_db()
    rows = conn.execute(
        "SELECT thread_id, title, created_at FROM conversations_threads WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,),
    ).fetchall()
    conn.close()
    return [_thread_row_to_dict(row) for row in rows]


def create_thread(user_id: int, title: str) -> int:
    title = title.strip() or "Untitled Thread"
    now = datetime.utcnow().isoformat()
    conn = _connect_db()
    with conn:
        cursor = conn.execute(
            "INSERT INTO conversations_threads (user_id, title, created_at) VALUES (?, ?, ?)",
            (user_id, title, now),
        )
        thread_id = cursor.lastrowid
    conn.close()
    return thread_id


def update_thread_title(thread_id: int, title: str) -> bool:
    conn = _connect_db()
    with conn:
        cursor = conn.execute(
            "UPDATE conversations_threads SET title = ? WHERE thread_id = ?",
            (title.strip() or "Untitled Thread", thread_id),
        )
        updated = cursor.rowcount > 0
    conn.close()
    return updated


def delete_thread(thread_id: int) -> None:
    conn = _connect_db()
    with conn:
        conn.execute("DELETE FROM messages WHERE thread_id = ?", (thread_id,))
        conn.execute("DELETE FROM conversations_threads WHERE thread_id = ?", (thread_id,))
    conn.close()


def get_thread(thread_id: int) -> sqlite3.Row | None:
    conn = _connect_db()
    row = conn.execute("SELECT thread_id, title, created_at FROM conversations_threads WHERE thread_id = ?", (thread_id,)).fetchone()
    conn.close()
    return row


def add_message(thread_id: int, sender: str, content: str) -> int:
    now = datetime.utcnow().isoformat()
    conn = _connect_db()
    with conn:
        cursor = conn.execute(
            "INSERT INTO messages (thread_id, sender, content, timestamp) VALUES (?, ?, ?, ?)",
            (thread_id, sender, content.strip(), now),
        )
        message_id = cursor.lastrowid
    conn.close()
    return message_id


def get_messages_for_thread(thread_id: int) -> list[dict]:
    conn = _connect_db()
    rows = conn.execute(
        "SELECT sender, content, timestamp FROM messages WHERE thread_id = ? ORDER BY message_id",
        (thread_id,),
    ).fetchall()
    conn.close()
    return [
        {
            "sender": row["sender"],
            "content": row["content"],
            "timestamp": row["timestamp"],
        }
        for row in rows
    ]
