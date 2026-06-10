# Imports
from datetime import datetime
from zoneinfo import ZoneInfo

# Import DB
from .connection import get_connection
from .users import ensure_user, get_user


PROMOTE_TIMEZONE = ZoneInfo("Asia/Seoul")


def _today_text() -> str:
    return str(datetime.now(PROMOTE_TIMEZONE).date())


def get_promote_info(user_id: int) -> tuple[int, str | None]:
    """Return today's promote count and the stored promote date."""
    ensure_user(user_id)
    user = get_user(user_id)
    last_date = user["last_promote_date"]
    today = _today_text()
    if last_date != today:
        return 0, last_date
    return user["promote_count"], last_date


def get_total_promote_count(user_id: int) -> int:
    """Return the total number of promotes used by the user."""
    user = get_user(user_id)
    return user["total_promote_count"] if user else 0


def complete_promote(user_id: int, cost: int, limit: int) -> tuple[bool, str, int, int]:
    """Charge and record one successful promotion atomically."""
    ensure_user(user_id)
    today = _today_text()

    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        user = conn.execute(
            """
            SELECT balance, promote_count, last_promote_date
            FROM users
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
        balance = user["balance"]
        used = user["promote_count"] if user["last_promote_date"] == today else 0

        if used >= limit:
            conn.commit()
            return False, "limit", used, balance
        if balance < cost:
            conn.commit()
            return False, "balance", used, balance

        new_used = used + 1
        new_balance = balance - cost
        conn.execute(
            """
            UPDATE users
            SET balance = ?,
                promote_count = ?,
                total_promote_count = total_promote_count + 1,
                last_promote_date = ?
            WHERE user_id = ?
            """,
            (new_balance, new_used, today, user_id),
        )
        conn.commit()

    return True, "ok", new_used, new_balance
