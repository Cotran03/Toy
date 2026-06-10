# Imports
import sqlite3
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# Import DB
from .connection import get_connection
from .users import ensure_user


WARNING_EXPIRE_DAYS = 30
WARNING_TIMEZONE = ZoneInfo("Asia/Seoul")


def _now_text() -> str:
    return datetime.now(WARNING_TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")


def _cutoff_text() -> str:
    cutoff = datetime.now(WARNING_TIMEZONE) - timedelta(days=WARNING_EXPIRE_DAYS)
    return cutoff.strftime("%Y-%m-%d %H:%M:%S")


def get_warnings(user_id: int) -> list[sqlite3.Row]:
    """Return non-expired warnings from the last 30 days."""
    cutoff = _cutoff_text()
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT *
            FROM warnings
            WHERE user_id = ? AND warned_at > ?
            ORDER BY warned_at DESC
            """,
            (user_id, cutoff),
        ).fetchall()


def get_warning_count(user_id: int) -> int:
    """Return the user's non-expired warning count."""
    return len(get_warnings(user_id))


def record_warnings_and_penalty(
    user_id: int,
    count: int,
    reason: str,
    penalty: int,
    banned: bool,
) -> int:
    """Record warnings, one command penalty, and ban state atomically."""
    if count < 1:
        raise ValueError("경고 수는 1 이상이어야 합니다.")

    ensure_user(user_id)
    warned_at = _now_text()
    with get_connection() as conn:
        conn.executemany(
            "INSERT INTO warnings (user_id, reason, warned_at) VALUES (?, ?, ?)",
            [(user_id, reason, warned_at)] * count,
        )
        conn.execute(
            """
            UPDATE users
            SET balance = MAX(0, balance - ?),
                is_banned = CASE WHEN ? = 1 THEN 1 ELSE is_banned END
            WHERE user_id = ?
            """,
            (penalty, 1 if banned else 0, user_id),
        )
        balance = conn.execute(
            "SELECT balance FROM users WHERE user_id = ?",
            (user_id,),
        ).fetchone()["balance"]
        conn.commit()
    return balance


def remove_warning(user_id: int) -> int:
    """Remove the most recent warning and return the updated warning count."""
    with get_connection() as conn:
        conn.execute(
            """
            DELETE FROM warnings
            WHERE id = (
                SELECT id
                FROM warnings
                WHERE user_id = ?
                ORDER BY warned_at DESC
                LIMIT 1
            )
            """,
            (user_id,),
        )
        conn.commit()
    return get_warning_count(user_id)


def expire_old_warnings() -> list[tuple[int, int]]:
    """Delete warnings older than 30 days, excluding users marked as banned."""
    cutoff = _cutoff_text()
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT w.user_id, COUNT(*) as cnt
            FROM warnings w
            LEFT JOIN users u ON w.user_id = u.user_id
            WHERE w.warned_at <= ?
              AND (u.is_banned IS NULL OR u.is_banned = 0)
            GROUP BY w.user_id
            """,
            (cutoff,),
        ).fetchall()

        conn.execute(
            """
            DELETE FROM warnings
            WHERE warned_at <= ?
              AND user_id IN (
                  SELECT user_id FROM users WHERE is_banned = 0
              )
            """,
            (cutoff,),
        )
        conn.commit()
    return [(row["user_id"], row["cnt"]) for row in rows]
