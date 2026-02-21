"""SQLite-backed feedback storage for public testing."""

from __future__ import annotations

import json
import sqlite3
from typing import Any


def init_db(db_path: str) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                message TEXT NOT NULL,
                rating INTEGER,
                contact TEXT,
                context_json TEXT,
                user_agent TEXT
            )
            """
        )
        conn.commit()


def save_feedback(
    db_path: str,
    *,
    message: str,
    rating: int | None = None,
    contact: str | None = None,
    context: dict[str, Any] | None = None,
    user_agent: str = "",
) -> int:
    context_json = json.dumps(context or {}, separators=(",", ":"), ensure_ascii=True)
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO feedback (message, rating, contact, context_json, user_agent)
            VALUES (?, ?, ?, ?, ?)
            """,
            (message, rating, contact, context_json, user_agent[:512]),
        )
        conn.commit()
        return int(cur.lastrowid)


def list_recent(db_path: str, limit: int = 50) -> list[dict[str, Any]]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT id, created_at, message, rating, contact, context_json
            FROM feedback
            ORDER BY id DESC
            LIMIT ?
            """,
            (max(1, min(limit, 200)),),
        ).fetchall()

    out: list[dict[str, Any]] = []
    for row in rows:
        try:
            context = json.loads(row["context_json"] or "{}")
        except json.JSONDecodeError:
            context = {}
        out.append(
            {
                "id": row["id"],
                "created_at": row["created_at"],
                "message": row["message"],
                "rating": row["rating"],
                "contact": row["contact"],
                "context": context,
            }
        )
    return out

