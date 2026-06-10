# Import DB
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


def complete_post_end(user_id: int, reward: int) -> tuple[int, int]:
    """Increment the end count and grant its reward atomically."""
    ensure_user(user_id)
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE users
            SET end_count = end_count + 1,
                balance = balance + ?
            WHERE user_id = ?
            """,
            (reward, user_id),
        )
        user = conn.execute(
            "SELECT end_count, balance FROM users WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        conn.commit()
    return user["end_count"], user["balance"]


def set_post_counts(user_id: int, post_count: int, end_count: int) -> tuple[int, int]:
    """Set the user's post counters and return the stored values."""
    if post_count < 0 or end_count < 0:
        raise ValueError("토론 횟수는 0 이상이어야 합니다.")
    if end_count > post_count:
        raise ValueError("종료한 토론 수는 게시한 토론 수보다 많을 수 없습니다.")

    ensure_user(user_id)
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET post_count = ?, end_count = ? WHERE user_id = ?",
            (post_count, end_count, user_id),
        )
        conn.commit()
    return get_post_count(user_id), get_end_count(user_id)
