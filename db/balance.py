# Import DB
from .connection import get_connection
from .users import ensure_user, get_user


def get_balance(user_id: int) -> int:
    """Return the user's INS balance."""
    user = get_user(user_id)
    return user["balance"] if user else 0


def add_balance(user_id: int, amount: int) -> int:
    """Add INS and return the updated balance."""
    ensure_user(user_id)
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET balance = balance + ? WHERE user_id = ?",
            (amount, user_id),
        )
        conn.commit()
    return get_balance(user_id)


def deduct_balance(user_id: int, amount: int) -> int:
    """Deduct INS without allowing the balance to go below zero."""
    ensure_user(user_id)
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET balance = MAX(0, balance - ?) WHERE user_id = ?",
            (amount, user_id),
        )
        conn.commit()
    return get_balance(user_id)


def set_balance(user_id: int, amount: int) -> int:
    """Set INS balance directly, clamped to zero or above."""
    ensure_user(user_id)
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET balance = MAX(0, ?) WHERE user_id = ?",
            (amount, user_id),
        )
        conn.commit()
    return get_balance(user_id)
