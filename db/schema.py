# Imports
import sqlite3

# Import DB
from .connection import get_connection


def init_db() -> None:
    """Create and migrate the SQLite tables used by the bot."""
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id              INTEGER PRIMARY KEY,
                balance              INTEGER NOT NULL DEFAULT 0,
                post_count           INTEGER NOT NULL DEFAULT 0,
                end_count            INTEGER NOT NULL DEFAULT 0,
                promote_count        INTEGER NOT NULL DEFAULT 0,
                total_promote_count  INTEGER NOT NULL DEFAULT 0,
                last_reward_date     TEXT,
                reward_streak        INTEGER NOT NULL DEFAULT 0,
                last_promote_date    TEXT,
                is_banned            INTEGER NOT NULL DEFAULT 0
            )
        """)

        migrations = [
            "ALTER TABLE users ADD COLUMN is_banned            INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE users ADD COLUMN promote_count        INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE users ADD COLUMN last_promote_date    TEXT",
            "ALTER TABLE users ADD COLUMN end_count            INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE users ADD COLUMN total_promote_count  INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE users ADD COLUMN reward_streak        INTEGER NOT NULL DEFAULT 0",
        ]
        for sql in migrations:
            try:
                cursor.execute(sql)
            except sqlite3.OperationalError:
                pass

        cursor.execute(
            """
            UPDATE users
            SET reward_streak = 1
            WHERE last_reward_date IS NOT NULL
              AND reward_streak = 0
            """
        )

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS warnings (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id   INTEGER NOT NULL,
                reason    TEXT,
                warned_at TEXT NOT NULL DEFAULT (datetime('now', '+9 hours')),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                name       TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT (datetime('now', '+9 hours'))
            )
        """)

        warning_timezone_migration = "warnings_warned_at_utc_to_kst"
        migration_applied = cursor.execute(
            "SELECT 1 FROM schema_migrations WHERE name = ?",
            (warning_timezone_migration,),
        ).fetchone()
        if migration_applied is None:
            # Existing first-server warnings were stored by SQLite in UTC.
            cursor.execute("UPDATE warnings SET warned_at = datetime(warned_at, '+9 hours')")
            cursor.execute(
                "INSERT INTO schema_migrations (name) VALUES (?)",
                (warning_timezone_migration,),
            )

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS economy_settings (
                key        TEXT PRIMARY KEY,
                value      INTEGER NOT NULL CHECK(value >= 0),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)

        conn.commit()

    print("[DB] 초기화 완료")
