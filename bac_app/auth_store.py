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
                is_male INTEGER,
                default_weight_lb REAL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        # Lightweight migration for older DBs created before profile columns existed.
        cols = {row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
        if "is_male" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN is_male INTEGER")
        if "default_weight_lb" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN default_weight_lb REAL")
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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_social_settings (
                user_id INTEGER PRIMARY KEY,
                share_with_friends INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS friend_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_user_id INTEGER NOT NULL,
                to_user_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                responded_at TEXT,
                UNIQUE(from_user_id, to_user_id),
                FOREIGN KEY(from_user_id) REFERENCES users(id),
                FOREIGN KEY(to_user_id) REFERENCES users(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS friendships (
                user_id INTEGER NOT NULL,
                friend_user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                PRIMARY KEY (user_id, friend_user_id),
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(friend_user_id) REFERENCES users(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_presence (
                user_id INTEGER PRIMARY KEY,
                bac_now REAL NOT NULL DEFAULT 0.0,
                drink_count INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )
        conn.commit()


def create_user(
    db_path: str,
    *,
    email: str,
    password: str,
    display_name: str,
    is_male: bool,
    default_weight_lb: float,
) -> dict[str, Any] | None:
    password_hash = generate_password_hash(password)
    try:
        with sqlite3.connect(db_path) as conn:
            cur = conn.execute(
                """
                INSERT INTO users (email, password_hash, display_name, is_male, default_weight_lb)
                VALUES (?, ?, ?, ?, ?)
                """,
                (email.lower().strip(), password_hash, display_name.strip(), int(bool(is_male)), float(default_weight_lb)),
            )
            conn.commit()
            user_id = int(cur.lastrowid)
    except sqlite3.IntegrityError:
        return None

    return {
        "id": user_id,
        "email": email.lower().strip(),
        "display_name": display_name.strip(),
        "is_male": bool(is_male),
        "default_weight_lb": float(default_weight_lb),
    }


def authenticate_user(db_path: str, *, email: str, password: str) -> dict[str, Any] | None:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT id, email, display_name, is_male, default_weight_lb, password_hash FROM users WHERE email = ?",
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

    return {
        "id": row["id"],
        "email": row["email"],
        "display_name": row["display_name"],
        "is_male": bool(row["is_male"]) if row["is_male"] is not None else True,
        "default_weight_lb": row["default_weight_lb"],
    }


def get_user_by_id(db_path: str, user_id: int) -> dict[str, Any] | None:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT id, email, display_name, is_male, default_weight_lb FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    if row is None:
        return None
    return {
        "id": row["id"],
        "email": row["email"],
        "display_name": row["display_name"],
        "is_male": bool(row["is_male"]) if row["is_male"] is not None else True,
        "default_weight_lb": row["default_weight_lb"],
    }


def save_user_session(db_path: str, *, user_id: int, name: str, payload: dict[str, Any]) -> int:
    payload_json = json.dumps(payload, separators=(",", ":"), ensure_ascii=True)
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO saved_sessions (user_id, name, payload_json) VALUES (?, ?, ?)",
            (user_id, name.strip(), payload_json),
        )
        conn.commit()
        return int(cur.lastrowid)


def list_user_sessions(
    db_path: str,
    *,
    user_id: int,
    limit: int = 200,
    session_date: str | None = None,
) -> list[dict[str, Any]]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        if session_date:
            rows = conn.execute(
                """
                SELECT id, name, created_at, payload_json, date(created_at) AS session_date
                FROM saved_sessions
                WHERE user_id = ? AND date(created_at) = ?
                ORDER BY rowid DESC
                LIMIT ?
                """,
                (user_id, session_date, max(1, min(limit, 200))),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, name, created_at, payload_json, date(created_at) AS session_date
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
                "session_date": row["session_date"],
                "drink_count": len(events) if isinstance(events, list) else 0,
            }
        )
    return out


def list_session_dates(db_path: str, *, user_id: int, limit: int = 120) -> list[dict[str, Any]]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT date(created_at) AS session_date, COUNT(*) AS session_count
            FROM saved_sessions
            WHERE user_id = ?
            GROUP BY date(created_at)
            ORDER BY session_date DESC
            LIMIT ?
            """,
            (user_id, max(1, min(limit, 366))),
        ).fetchall()
    return [{"session_date": row["session_date"], "session_count": row["session_count"]} for row in rows]


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


def find_user_by_email(db_path: str, *, email: str) -> dict[str, Any] | None:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT id, email, display_name FROM users WHERE email = ?",
            (email.strip().lower(),),
        ).fetchone()
    if row is None:
        return None
    return {"id": row["id"], "email": row["email"], "display_name": row["display_name"]}


def set_share_with_friends(db_path: str, *, user_id: int, enabled: bool) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO user_social_settings (user_id, share_with_friends, updated_at)
            VALUES (?, ?, datetime('now'))
            ON CONFLICT(user_id) DO UPDATE SET
              share_with_friends=excluded.share_with_friends,
              updated_at=datetime('now')
            """,
            (user_id, 1 if enabled else 0),
        )
        conn.commit()


def get_share_with_friends(db_path: str, *, user_id: int) -> bool:
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT share_with_friends FROM user_social_settings WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    if row is None:
        return False
    return bool(row[0])


def upsert_presence(db_path: str, *, user_id: int, bac_now: float, drink_count: int) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO user_presence (user_id, bac_now, drink_count, updated_at)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(user_id) DO UPDATE SET
              bac_now=excluded.bac_now,
              drink_count=excluded.drink_count,
              updated_at=datetime('now')
            """,
            (user_id, float(bac_now), int(drink_count)),
        )
        conn.commit()


def list_friends(db_path: str, *, user_id: int) -> list[dict[str, Any]]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT u.id, u.display_name, u.email
            FROM friendships f
            JOIN users u ON u.id = f.friend_user_id
            WHERE f.user_id = ?
            ORDER BY u.display_name COLLATE NOCASE ASC
            """,
            (user_id,),
        ).fetchall()
    return [{"id": r["id"], "display_name": r["display_name"], "email": r["email"]} for r in rows]


def are_friends(db_path: str, *, user_a: int, user_b: int) -> bool:
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT 1 FROM friendships WHERE user_id = ? AND friend_user_id = ?",
            (user_a, user_b),
        ).fetchone()
    return row is not None


def send_friend_request(db_path: str, *, from_user_id: int, to_user_id: int) -> tuple[bool, str]:
    if from_user_id == to_user_id:
        return False, "You cannot friend yourself."
    if are_friends(db_path, user_a=from_user_id, user_b=to_user_id):
        return False, "Already friends."
    with sqlite3.connect(db_path) as conn:
        pending = conn.execute(
            """
            SELECT id FROM friend_requests
            WHERE ((from_user_id = ? AND to_user_id = ?) OR (from_user_id = ? AND to_user_id = ?))
              AND status = 'pending'
            """,
            (from_user_id, to_user_id, to_user_id, from_user_id),
        ).fetchone()
        if pending is not None:
            return False, "A pending request already exists."
        conn.execute(
            "INSERT INTO friend_requests (from_user_id, to_user_id, status) VALUES (?, ?, 'pending')",
            (from_user_id, to_user_id),
        )
        conn.commit()
    return True, "Request sent."


def list_incoming_friend_requests(db_path: str, *, user_id: int) -> list[dict[str, Any]]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT fr.id, fr.created_at, u.id as from_user_id, u.display_name, u.email
            FROM friend_requests fr
            JOIN users u ON u.id = fr.from_user_id
            WHERE fr.to_user_id = ? AND fr.status = 'pending'
            ORDER BY fr.id DESC
            """,
            (user_id,),
        ).fetchall()
    return [
        {
            "request_id": r["id"],
            "created_at": r["created_at"],
            "from_user_id": r["from_user_id"],
            "display_name": r["display_name"],
            "email": r["email"],
        }
        for r in rows
    ]


def respond_friend_request(db_path: str, *, user_id: int, request_id: int, accept: bool) -> tuple[bool, str]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        req = conn.execute(
            "SELECT id, from_user_id, to_user_id, status FROM friend_requests WHERE id = ?",
            (request_id,),
        ).fetchone()
        if req is None or req["to_user_id"] != user_id:
            return False, "Request not found."
        if req["status"] != "pending":
            return False, "Request already handled."

        if accept:
            conn.execute(
                "UPDATE friend_requests SET status = 'accepted', responded_at = datetime('now') WHERE id = ?",
                (request_id,),
            )
            conn.execute(
                "INSERT OR IGNORE INTO friendships (user_id, friend_user_id) VALUES (?, ?)",
                (req["from_user_id"], req["to_user_id"]),
            )
            conn.execute(
                "INSERT OR IGNORE INTO friendships (user_id, friend_user_id) VALUES (?, ?)",
                (req["to_user_id"], req["from_user_id"]),
            )
            conn.commit()
            return True, "Friend request accepted."

        conn.execute(
            "UPDATE friend_requests SET status = 'rejected', responded_at = datetime('now') WHERE id = ?",
            (request_id,),
        )
        conn.commit()
        return True, "Friend request rejected."


def list_friend_feed(db_path: str, *, user_id: int) -> list[dict[str, Any]]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT u.id, u.display_name, u.email, p.bac_now, p.drink_count, p.updated_at
            FROM friendships f
            JOIN users u ON u.id = f.friend_user_id
            LEFT JOIN user_social_settings s ON s.user_id = u.id
            LEFT JOIN user_presence p ON p.user_id = u.id
            WHERE f.user_id = ?
              AND COALESCE(s.share_with_friends, 0) = 1
            ORDER BY p.updated_at DESC, u.display_name COLLATE NOCASE ASC
            """,
            (user_id,),
        ).fetchall()
    out = []
    for r in rows:
        out.append(
            {
                "user_id": r["id"],
                "display_name": r["display_name"],
                "email": r["email"],
                "bac_now": float(r["bac_now"]) if r["bac_now"] is not None else None,
                "drink_count": int(r["drink_count"]) if r["drink_count"] is not None else None,
                "updated_at": r["updated_at"],
            }
        )
    return out
