# Imports
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

# Import DB
from .connection import get_connection
from .users import ensure_user, get_user


REWARD_TIMEZONE = ZoneInfo("Asia/Seoul")


def _today() -> date:
    return datetime.now(REWARD_TIMEZONE).date()


def _parse_reward_date(value: str | None) -> date | None:
    if not value:
        return None

    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def get_reward_streak(user_id: int) -> int:
    """Return the user's current daily reward streak."""
    user = get_user(user_id)
    last_reward_date = _parse_reward_date(user["last_reward_date"] if user else None)
    if last_reward_date is None:
        return 0

    today = _today()
    if last_reward_date not in (today, today - timedelta(days=1)):
        return 0

    return user["reward_streak"] if user else 0


def get_last_reward_date(user_id: int) -> str | None:
    """Return the user's last reward claim date."""
    user = get_user(user_id)
    last_reward_date = _parse_reward_date(user["last_reward_date"] if user else None)
    return last_reward_date.isoformat() if last_reward_date else None


def claim_reward(user_id: int, amount: int) -> tuple[bool, int, int]:
    """Claim the daily reward atomically.

    Returns (claimed, current_balance, reward_streak).
    """
    ensure_user(user_id)
    today = _today()

    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        user = conn.execute(
            "SELECT balance, last_reward_date, reward_streak FROM users WHERE user_id = ?",
            (user_id,),
        ).fetchone()

        last_reward_date = _parse_reward_date(user["last_reward_date"] if user else None)
        current_balance = user["balance"] if user else 0
        current_streak = user["reward_streak"] if user else 0

        if last_reward_date == today:
            conn.commit()
            return False, current_balance, current_streak

        next_streak = current_streak + 1 if last_reward_date == today - timedelta(days=1) else 1
        new_balance = current_balance + amount
        conn.execute(
            """
            UPDATE users
            SET balance = ?, last_reward_date = ?, reward_streak = ?
            WHERE user_id = ?
            """,
            (new_balance, str(today), next_streak, user_id),
        )
        conn.commit()

    return True, new_balance, next_streak
