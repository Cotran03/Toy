import os
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


SECONDARY_WARN_DB_PATH = os.path.join(os.path.dirname(__file__), "secondary_warn.db")
SECONDARY_WARN_DB_LOCK = threading.RLock()
WARNING_TIMEZONE = ZoneInfo("Asia/Seoul")


@contextmanager
def secondary_warn_connection() -> Iterator[sqlite3.Connection]:
    with SECONDARY_WARN_DB_LOCK:
        conn = sqlite3.connect(SECONDARY_WARN_DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            conn.close()


def _cutoff(expire_days: int) -> str | None:
    if expire_days <= 0:
        return None
    cutoff = datetime.now(WARNING_TIMEZONE) - timedelta(days=expire_days)
    return cutoff.strftime("%Y-%m-%d %H:%M:%S")


def _now_text() -> str:
    return datetime.now(WARNING_TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")


def init_secondary_warn_db() -> None:
    with secondary_warn_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                is_banned INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        try:
            conn.execute("ALTER TABLE users ADD COLUMN is_banned INTEGER NOT NULL DEFAULT 0")
        except sqlite3.OperationalError:
            pass
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS warnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                reason TEXT,
                warned_at TEXT NOT NULL DEFAULT (datetime('now', '+9 hours')),
                moderator_id INTEGER,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
            """
        )
        conn.commit()


def ensure_secondary_user(user_id: int) -> None:
    with secondary_warn_connection() as conn:
        conn.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        conn.commit()


def set_secondary_banned(user_id: int, is_banned: bool) -> None:
    ensure_secondary_user(user_id)
    with secondary_warn_connection() as conn:
        conn.execute(
            "UPDATE users SET is_banned = ? WHERE user_id = ?",
            (1 if is_banned else 0, user_id),
        )
        conn.commit()


def get_secondary_warnings(user_id: int, expire_days: int) -> list[sqlite3.Row]:
    cutoff = _cutoff(expire_days)
    with secondary_warn_connection() as conn:
        if cutoff is None:
            return conn.execute(
                """
                SELECT *
                FROM warnings
                WHERE user_id = ?
                ORDER BY datetime(warned_at) DESC, id DESC
                """,
                (user_id,),
            ).fetchall()

        return conn.execute(
            """
            SELECT *
            FROM warnings
            WHERE user_id = ? AND datetime(warned_at) > datetime(?)
            ORDER BY datetime(warned_at) DESC, id DESC
            """,
            (user_id, cutoff),
        ).fetchall()


def get_secondary_warning_count(user_id: int, expire_days: int) -> int:
    return len(get_secondary_warnings(user_id, expire_days))


def add_secondary_warning(user_id: int, reason: str, moderator_id: int, expire_days: int) -> int:
    ensure_secondary_user(user_id)
    with secondary_warn_connection() as conn:
        conn.execute(
            "INSERT INTO warnings (user_id, reason, warned_at, moderator_id) VALUES (?, ?, ?, ?)",
            (user_id, reason, _now_text(), moderator_id),
        )
        conn.commit()
    return get_secondary_warning_count(user_id, expire_days)


def remove_secondary_warning(user_id: int, expire_days: int) -> int:
    with secondary_warn_connection() as conn:
        conn.execute(
            """
            DELETE FROM warnings
            WHERE id = (
                SELECT id
                FROM warnings
                WHERE user_id = ?
                ORDER BY datetime(warned_at) DESC, id DESC
                LIMIT 1
            )
            """,
            (user_id,),
        )
        conn.commit()
    return get_secondary_warning_count(user_id, expire_days)


def expire_secondary_warnings(expire_days: int) -> list[tuple[int, int]]:
    cutoff = _cutoff(expire_days)
    if cutoff is None:
        return []

    with secondary_warn_connection() as conn:
        rows = conn.execute(
            """
            SELECT user_id, COUNT(*) as cnt
            FROM warnings
            WHERE datetime(warned_at) <= datetime(?)
              AND user_id IN (
                  SELECT user_id
                  FROM users
                  WHERE is_banned = 0
              )
            GROUP BY user_id
            """,
            (cutoff,),
        ).fetchall()
        conn.execute(
            """
            DELETE FROM warnings
            WHERE datetime(warned_at) <= datetime(?)
              AND user_id IN (
                  SELECT user_id
                  FROM users
                  WHERE is_banned = 0
              )
            """,
            (cutoff,),
        )
        conn.commit()
    return [(row["user_id"], row["cnt"]) for row in rows]
