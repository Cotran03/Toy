# Imports
import discord

# Import Config
from config import DAILY_REWARD_AMOUNT, ROLE_PROMOTER, ROLE_PROMOTER_ADVANCED, STORE_ITEMS

# Import DB
from db.database import (
    add_balance,
    claim_reward,
    deduct_balance,
    ensure_user,
    get_balance,
    get_last_reward_date,
    set_balance,
)


def get_user_balance(user_id: int) -> int:
    ensure_user(user_id)
    return get_balance(user_id)


def claim_daily_reward(user_id: int) -> tuple[bool, int, int, str | None]:
    """Claim the daily reward.

    Returns (claimed, current_balance, reward_streak, last_reward_date).
    """
    claimed, current_balance, reward_streak = claim_reward(user_id, DAILY_REWARD_AMOUNT)
    return claimed, current_balance, reward_streak, get_last_reward_date(user_id)


def add_user_balance(user_id: int, amount: int) -> int:
    ensure_user(user_id)
    return add_balance(user_id, amount)


def deduct_user_balance(user_id: int, amount: int) -> int:
    ensure_user(user_id)
    return deduct_balance(user_id, amount)


def reset_user_balance(user_id: int) -> int:
    ensure_user(user_id)
    return set_balance(user_id, 0)


def can_purchase_store_role(
    member: discord.Member,
    guild: discord.Guild,
    role_id: int,
) -> tuple[bool, str, discord.Role | None, dict | None, int]:
    """Validate a store role purchase.

    Returns (can_purchase, reason, role, item, current_balance).
    """
    role = guild.get_role(role_id)
    item = STORE_ITEMS.get(role_id)
    balance = get_user_balance(member.id)

    if role is None or item is None:
        return False, "not_found", role, item, balance

    if role in member.roles:
        return False, "already_owned", role, item, balance

    if balance < item["price"]:
        return False, "insufficient_balance", role, item, balance

    role_ids = {owned_role.id for owned_role in member.roles}
    if role_id == ROLE_PROMOTER_ADVANCED and ROLE_PROMOTER not in role_ids:
        return False, "missing_promoter", role, item, balance

    return True, "ok", role, item, balance


def complete_store_purchase(user_id: int, price: int) -> int:
    return deduct_user_balance(user_id, price)
