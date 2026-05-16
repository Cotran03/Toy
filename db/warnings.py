# Imports
import sqlite3
from datetime import datetime, timedelta

# Import DB
from .connection import get_connection
from .users import ensure_user


def get_warnings(user_id: int) -> list[sqlite3.Row]:
    """Return non-expired warnings from the last 30 days."""
    cutoff = datetime.now() - timedelta(days=30)
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT *
            FROM warnings
            WHERE user_id = ? AND warned_at > ?
            ORDER BY warned_at DESC
            """,
            (user_id, cutoff.isoformat()),
        ).fetchall()


def get_warning_count(user_id: int) -> int:
    """Return the user's non-expired warning count."""
    return len(get_warnings(user_id))


def add_warning(user_id: int, reason: str = "") -> int:
    """Add a warning and return the updated warning count."""
    ensure_user(user_id)
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO warnings (user_id, reason) VALUES (?, ?)",
            (user_id, reason),
        )
        conn.commit()
    return get_warning_count(user_id)


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


def clear_warnings(user_id: int) -> None:
    """Remove all warnings for a user."""
    with get_connection() as conn:
        conn.execute("DELETE FROM warnings WHERE user_id = ?", (user_id,))
        conn.commit()


def expire_old_warnings() -> list[tuple[int, int]]:
    """Delete warnings older than 30 days, excluding users marked as banned."""
    cutoff = datetime.now() - timedelta(days=30)
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
            (cutoff.isoformat(),),
        ).fetchall()

        conn.execute(
            """
            DELETE FROM warnings
            WHERE warned_at <= ?
              AND user_id IN (
                  SELECT user_id FROM users WHERE is_banned = 0
              )
            """,
            (cutoff.isoformat(),),
        )
        conn.commit()
    return [(row["user_id"], row["cnt"]) for row in rows]
