import time

from config.post import (
    POST_ACTIVE_LIMIT,
    POST_ACTIVE_LIMIT_MULTITASKER,
    POST_COUNT_EXCLUDED_FORUM_CHANNELS,
)
from config.promote import PROMOTE_ADVANCED_DAILY_LIMIT, PROMOTE_DAILY_LIMIT

from .connection import get_connection


DISCUSSION_SETTING_DEFAULTS = {
    "post_active_limit": POST_ACTIVE_LIMIT,
    "post_active_limit_multitasker": POST_ACTIVE_LIMIT_MULTITASKER,
    "promote_daily_limit": PROMOTE_DAILY_LIMIT,
    "promote_advanced_daily_limit": PROMOTE_ADVANCED_DAILY_LIMIT,
}
DEFAULT_EXCLUDED_FORUM_IDS = frozenset(POST_COUNT_EXCLUDED_FORUM_CHANNELS)


def get_discussion_setting(key: str) -> int:
    if key not in DISCUSSION_SETTING_DEFAULTS:
        raise KeyError(key)

    with get_connection() as conn:
        row = conn.execute(
            "SELECT value FROM discussion_settings WHERE key = ?",
            (key,),
        ).fetchone()

    return row["value"] if row else DISCUSSION_SETTING_DEFAULTS[key]


def get_all_discussion_settings() -> dict[str, int]:
    return {key: get_discussion_setting(key) for key in DISCUSSION_SETTING_DEFAULTS}


def set_discussion_setting(key: str, value: int) -> int:
    if key not in DISCUSSION_SETTING_DEFAULTS:
        raise KeyError(key)
    if value < 1:
        raise ValueError("설정값은 1 이상이어야 합니다.")

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO discussion_settings (key, value, updated_at)
            VALUES (?, ?, datetime('now', '+9 hours'))
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            (key, value),
        )
        conn.commit()

    return value


def reset_discussion_setting(key: str) -> int:
    if key not in DISCUSSION_SETTING_DEFAULTS:
        raise KeyError(key)

    with get_connection() as conn:
        conn.execute("DELETE FROM discussion_settings WHERE key = ?", (key,))
        conn.commit()

    return DISCUSSION_SETTING_DEFAULTS[key]


def get_forum_exclusion(forum_id: int) -> bool:
    with get_connection() as conn:
        deleted = conn.execute(
            "SELECT 1 FROM discussion_deleted_forums WHERE forum_id = ?",
            (forum_id,),
        ).fetchone()
        open_period = conn.execute(
            """
            SELECT 1
            FROM discussion_forum_exclusion_periods
            WHERE forum_id = ? AND ended_at IS NULL
            LIMIT 1
            """,
            (forum_id,),
        ).fetchone()
        has_history = conn.execute(
            "SELECT 1 FROM discussion_forum_exclusion_periods WHERE forum_id = ? LIMIT 1",
            (forum_id,),
        ).fetchone()

    if deleted is not None:
        return False
    if open_period is not None:
        return True
    if has_history is not None:
        return False

    return forum_id in DEFAULT_EXCLUDED_FORUM_IDS


def is_forum_excluded_at(forum_id: int, created_at: int) -> bool:
    with get_connection() as conn:
        deleted = conn.execute(
            "SELECT 1 FROM discussion_deleted_forums WHERE forum_id = ?",
            (forum_id,),
        ).fetchone()
        matching_period = conn.execute(
            """
            SELECT 1
            FROM discussion_forum_exclusion_periods
            WHERE forum_id = ?
              AND started_at <= ?
              AND (ended_at IS NULL OR ended_at > ?)
            LIMIT 1
            """,
            (forum_id, created_at, created_at),
        ).fetchone()
        has_history = conn.execute(
            "SELECT 1 FROM discussion_forum_exclusion_periods WHERE forum_id = ? LIMIT 1",
            (forum_id,),
        ).fetchone()

    if deleted is not None:
        return False
    if matching_period is not None:
        return True
    if has_history is not None:
        return False

    return forum_id in DEFAULT_EXCLUDED_FORUM_IDS


def get_excluded_forum_ids() -> set[int]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT DISTINCT forum_id FROM discussion_forum_exclusion_periods"
        ).fetchall()

    forum_ids = DEFAULT_EXCLUDED_FORUM_IDS | {row["forum_id"] for row in rows}
    return {forum_id for forum_id in forum_ids if get_forum_exclusion(forum_id)}


def delete_forum_exclusion_history(forum_id: int) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM discussion_forum_exclusion_periods WHERE forum_id = ?",
            (forum_id,),
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO discussion_deleted_forums (forum_id)
            VALUES (?)
            """,
            (forum_id,),
        )
        conn.commit()
    return cursor.rowcount


def set_forum_excluded(forum_id: int, excluded: bool) -> bool:
    if get_forum_exclusion(forum_id) == excluded:
        return False

    now = time.time_ns() // 1_000_000
    with get_connection() as conn:
        conn.execute("DELETE FROM discussion_deleted_forums WHERE forum_id = ?", (forum_id,))
        if excluded:
            conn.execute(
                """
                INSERT INTO discussion_forum_exclusion_periods (forum_id, started_at)
                VALUES (?, ?)
                """,
                (forum_id, now),
            )
        else:
            closed = conn.execute(
                """
                UPDATE discussion_forum_exclusion_periods
                SET ended_at = ?
                WHERE forum_id = ? AND ended_at IS NULL
                """,
                (now, forum_id),
            )
            if closed.rowcount == 0:
                conn.execute(
                    """
                    INSERT INTO discussion_forum_exclusion_periods (forum_id, started_at, ended_at)
                    VALUES (?, 0, ?)
                    """,
                    (forum_id, now),
                )
        conn.commit()

    return True
