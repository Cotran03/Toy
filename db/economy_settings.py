from config.economy import (
    DAILY_REWARD_AMOUNT,
    END_REWARD_AMOUNT,
    PROMOTE_COST,
    WARN_PENALTY,
)
from config.store import STORE_ITEMS

from .connection import get_connection


ECONOMY_SETTING_DEFAULTS = {
    "daily_reward": DAILY_REWARD_AMOUNT,
    "end_reward": END_REWARD_AMOUNT,
    "warn_penalty": WARN_PENALTY,
    "promote_cost": PROMOTE_COST,
}
STORE_PRICE_PREFIX = "store_price:"


def get_economy_setting(key: str) -> int:
    if key not in ECONOMY_SETTING_DEFAULTS:
        raise KeyError(key)

    with get_connection() as conn:
        row = conn.execute(
            "SELECT value FROM economy_settings WHERE key = ?",
            (key,),
        ).fetchone()

    return row["value"] if row else ECONOMY_SETTING_DEFAULTS[key]


def get_all_economy_settings() -> dict[str, int]:
    return {key: get_economy_setting(key) for key in ECONOMY_SETTING_DEFAULTS}


def set_economy_setting(key: str, value: int) -> int:
    if key not in ECONOMY_SETTING_DEFAULTS:
        raise KeyError(key)
    if value < 0:
        raise ValueError("설정값은 0 이상이어야 합니다.")

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO economy_settings (key, value, updated_at)
            VALUES (?, ?, datetime('now'))
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            (key, value),
        )
        conn.commit()

    return value


def reset_economy_setting(key: str) -> int:
    if key not in ECONOMY_SETTING_DEFAULTS:
        raise KeyError(key)

    with get_connection() as conn:
        conn.execute("DELETE FROM economy_settings WHERE key = ?", (key,))
        conn.commit()

    return ECONOMY_SETTING_DEFAULTS[key]


def _store_price_key(role_id: int) -> str:
    return f"{STORE_PRICE_PREFIX}{role_id}"


def get_store_price(role_id: int) -> int:
    item = STORE_ITEMS.get(role_id)
    if item is None:
        raise KeyError(role_id)

    with get_connection() as conn:
        row = conn.execute(
            "SELECT value FROM economy_settings WHERE key = ?",
            (_store_price_key(role_id),),
        ).fetchone()

    return row["value"] if row else item["price"]


def get_store_items() -> dict[int, dict]:
    items = {role_id: item.copy() for role_id, item in STORE_ITEMS.items()}
    keys = [_store_price_key(role_id) for role_id in items]
    placeholders = ", ".join("?" for _ in keys)

    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT key, value FROM economy_settings WHERE key IN ({placeholders})",
            keys,
        ).fetchall()

    overrides = {row["key"]: row["value"] for row in rows}
    for role_id, item in items.items():
        item["price"] = overrides.get(_store_price_key(role_id), item["price"])

    return items


def set_store_price(role_id: int, price: int) -> int:
    if role_id not in STORE_ITEMS:
        raise KeyError(role_id)
    if price < 0:
        raise ValueError("가격은 0 이상이어야 합니다.")

    key = _store_price_key(role_id)
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO economy_settings (key, value, updated_at)
            VALUES (?, ?, datetime('now'))
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            (key, price),
        )
        conn.commit()

    return price


def reset_store_price(role_id: int) -> int:
    item = STORE_ITEMS.get(role_id)
    if item is None:
        raise KeyError(role_id)

    with get_connection() as conn:
        conn.execute(
            "DELETE FROM economy_settings WHERE key = ?",
            (_store_price_key(role_id),),
        )
        conn.commit()

    return item["price"]
