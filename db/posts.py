from .connection import get_connection
from .users import ensure_user, get_user


def get_post_count(user_id: int) -> int:
    """Return the number of posts created by the user."""
    user = get_user(user_id)
    return user["post_count"] if user else 0


def increment_post_count(user_id: int) -> int:
    """Increment created post count and return the updated value."""
    ensure_user(user_id)
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET post_count = post_count + 1 WHERE user_id = ?",
            (user_id,),
        )
        conn.commit()
    return get_post_count(user_id)


def get_end_count(user_id: int) -> int:
    """Return the number of ended posts for the user."""
    user = get_user(user_id)
    return user["end_count"] if user else 0


def get_active_post_count(user_id: int) -> int:
    """Return created posts minus ended posts, clamped to zero."""
    active = get_post_count(user_id) - get_end_count(user_id)
    return active if active > 0 else 0


def increment_end_count(user_id: int) -> int:
    """Increment ended post count and return the updated value."""
    ensure_user(user_id)
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET end_count = end_count + 1 WHERE user_id = ?",
            (user_id,),
        )
        conn.commit()
    return get_end_count(user_id)
