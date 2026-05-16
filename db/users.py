# Imports
import sqlite3

# Import DB
from .connection import get_connection


def get_user(user_id: int) -> sqlite3.Row | None:
    """Return a user row, or None if the user does not exist."""
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE user_id = ?",
            (user_id,),
        ).fetchone()


def ensure_user(user_id: int) -> None:
    """Create the user row with defaults if it does not exist."""
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users (user_id) VALUES (?)",
            (user_id,),
        )
        conn.commit()
