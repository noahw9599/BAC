"""SQLite-backed user auth and per-user saved BAC sessions."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from werkzeug.security import check_password_hash, generate_password_hash


def init_db(db_path: str) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                display_name TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS saved_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_saved_sessions_user_id ON saved_sessions(user_id)")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_favorites (
                user_id INTEGER NOT NULL,
                catalog_id TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                PRIMARY KEY (user_id, catalog_id),
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )
        conn.commit()


def create_user(db_path: str, *, email: str, password: str, display_name: str) -> dict[str, Any] | None:
    password_hash = generate_password_hash(password)
    try:
        with sqlite3.connect(db_path) as conn:
            cur = conn.execute(
                "INSERT INTO users (email, password_hash, display_name) VALUES (?, ?, ?)",
                (email.lower().strip(), password_hash, display_name.strip()),
            )
            conn.commit()
            user_id = int(cur.lastrowid)
    except sqlite3.IntegrityError:
        return None

    return {"id": user_id, "email": email.lower().strip(), "display_name": display_name.strip()}


def authenticate_user(db_path: str, *, email: str, password: str) -> dict[str, Any] | None:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT id, email, display_name, password_hash FROM users WHERE email = ?",
            (email.lower().strip(),),
        ).fetchone()

    if row is None:
        return None
    try:
        ok = check_password_hash(row["password_hash"], password)
    except ValueError:
        return None
    if not ok:
        return None

    return {"id": row["id"], "email": row["email"], "display_name": row["display_name"]}


def get_user_by_id(db_path: str, user_id: int) -> dict[str, Any] | None:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT id, email, display_name FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    if row is None:
        return None
    return {"id": row["id"], "email": row["email"], "display_name": row["display_name"]}


def save_user_session(db_path: str, *, user_id: int, name: str, payload: dict[str, Any]) -> int:
    payload_json = json.dumps(payload, separators=(",", ":"), ensure_ascii=True)
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO saved_sessions (user_id, name, payload_json) VALUES (?, ?, ?)",
            (user_id, name.strip(), payload_json),
        )
        conn.commit()
        return int(cur.lastrowid)


def list_user_sessions(db_path: str, *, user_id: int, limit: int = 50) -> list[dict[str, Any]]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT id, name, created_at, payload_json
            FROM saved_sessions
            WHERE user_id = ?
            ORDER BY rowid DESC
            LIMIT ?
            """,
            (user_id, max(1, min(limit, 200))),
        ).fetchall()

    out = []
    for row in rows:
        try:
            payload = json.loads(row["payload_json"] or "{}")
        except json.JSONDecodeError:
            payload = {}
        events = payload.get("events", [])
        out.append(
            {
                "id": row["id"],
                "name": row["name"],
                "created_at": row["created_at"],
                "drink_count": len(events) if isinstance(events, list) else 0,
            }
        )
    return out


def get_user_session_payload(db_path: str, *, user_id: int, session_id: int) -> dict[str, Any] | None:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT payload_json
            FROM saved_sessions
            WHERE id = ? AND user_id = ?
            """,
            (session_id, user_id),
        ).fetchone()

    if row is None:
        return None
    try:
        return json.loads(row["payload_json"] or "{}")
    except json.JSONDecodeError:
        return None


def track_favorite_drink(db_path: str, *, user_id: int, catalog_id: str) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "DELETE FROM user_favorites WHERE user_id = ? AND catalog_id = ?",
            (user_id, catalog_id),
        )
        conn.execute(
            """
            INSERT INTO user_favorites (user_id, catalog_id, updated_at)
            VALUES (?, ?, datetime('now'))
            """,
            (user_id, catalog_id),
        )
        conn.commit()


def list_favorite_drinks(db_path: str, *, user_id: int, limit: int = 6) -> list[str]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT catalog_id
            FROM user_favorites
            WHERE user_id = ?
            ORDER BY rowid DESC
            LIMIT ?
            """,
            (user_id, max(1, min(limit, 20))),
        ).fetchall()
    return [row["catalog_id"] for row in rows]
