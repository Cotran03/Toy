import sqlite3

from .connection import get_connection


VERIFY_MESSAGE_ID_KEY = "verify_message_id"


def get_bot_setting(key: str) -> str | None:
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT value FROM bot_settings WHERE key = ?",
                (key,),
            ).fetchone()
    except sqlite3.OperationalError as exc:
        if "no such table: bot_settings" not in str(exc):
            raise
        return None
    return row["value"] if row else None


def set_bot_setting(key: str, value: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO bot_settings (key, value, updated_at)
            VALUES (?, ?, datetime('now', '+9 hours'))
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            (key, value),
        )
        conn.commit()


def get_verify_message_id(default: int = 0) -> int:
    value = get_bot_setting(VERIFY_MESSAGE_ID_KEY)
    if value is None:
        return default

    try:
        return int(value)
    except ValueError:
        return default


def set_verify_message_id(message_id: int) -> None:
    set_bot_setting(VERIFY_MESSAGE_ID_KEY, str(message_id))
