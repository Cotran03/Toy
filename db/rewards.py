from datetime import date

from .connection import get_connection
from .users import ensure_user, get_user


def can_claim_reward(user_id: int) -> bool:
    """Return True if the user has not claimed today's reward."""
    user = get_user(user_id)
    if not user or not user["last_reward_date"]:
        return True
    return user["last_reward_date"] != str(date.today())


def set_reward_claimed(user_id: int) -> None:
    """Mark today's daily reward as claimed."""
    ensure_user(user_id)
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET last_reward_date = ? WHERE user_id = ?",
            (str(date.today()), user_id),
        )
        conn.commit()
