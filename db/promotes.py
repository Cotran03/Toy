from datetime import date

from .connection import get_connection
from .users import ensure_user, get_user


def get_promote_info(user_id: int) -> tuple[int, str | None]:
    """Return today's promote count and the stored promote date."""
    ensure_user(user_id)
    user = get_user(user_id)
    last_date = user["last_promote_date"]
    today = str(date.today())
    if last_date != today:
        return 0, last_date
    return user["promote_count"], last_date


def get_total_promote_count(user_id: int) -> int:
    """Return the total number of promotes used by the user."""
    user = get_user(user_id)
    return user["total_promote_count"] if user else 0


def increment_promote(user_id: int) -> int:
    """Increment today's promote count and total promote count."""
    ensure_user(user_id)
    today = str(date.today())
    current_count, last_date = get_promote_info(user_id)
    new_count = 1 if last_date != today else current_count + 1

    with get_connection() as conn:
        conn.execute(
            """
            UPDATE users
            SET promote_count = ?,
                total_promote_count = total_promote_count + 1,
                last_promote_date = ?
            WHERE user_id = ?
            """,
            (new_count, today, user_id),
        )
        conn.commit()
    return new_count
