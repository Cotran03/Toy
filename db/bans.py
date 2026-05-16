# Import DB
from .connection import get_connection
from .users import ensure_user, get_user


def set_banned(user_id: int, banned: bool) -> None:
    """Set whether the user is currently banned by the warning system."""
    ensure_user(user_id)
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET is_banned = ? WHERE user_id = ?",
            (1 if banned else 0, user_id),
        )
        conn.commit()


def is_banned(user_id: int) -> bool:
    """Return whether the user is marked as banned."""
    user = get_user(user_id)
    return bool(user["is_banned"]) if user else False
