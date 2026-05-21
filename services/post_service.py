# Imports
import discord

# Import Config
from config import (
    END_REWARD_AMOUNT,
    POST_ACTIVE_LIMIT,
    POST_ACTIVE_LIMIT_MULTITASKER,
    POST_COUNT_EXCLUDED_FORUM_CHANNELS,
    POST_END_ROLES,
    PROMOTE_ADVANCED_DAILY_LIMIT,
    PROMOTE_COST,
    PROMOTE_DAILY_LIMIT,
    ROLE_MULTITASKER,
    ROLE_PROMOTER,
    ROLE_PROMOTER_ADVANCED,
    TAG_ENDED,
    TAG_ONGOING,
)

# Import DB
from db.database import (
    add_balance,
    deduct_balance,
    ensure_user,
    get_active_post_count,
    get_balance,
    get_promote_info,
    increment_end_count,
    increment_post_count,
    increment_promote,
)


def is_forum_post_channel(channel) -> bool:
    return (
        isinstance(channel, discord.Thread)
        and isinstance(channel.parent, discord.ForumChannel)
        and channel.parent.id not in POST_COUNT_EXCLUDED_FORUM_CHANNELS
    )


def can_end_post(member: discord.Member, channel: discord.Thread) -> bool:
    is_owner = channel.owner_id == member.id
    has_end_role = any(role.id in POST_END_ROLES for role in member.roles)
    return is_owner or has_end_role


def build_ended_tags(channel: discord.Thread) -> tuple[list[discord.ForumTag] | None, str | None]:
    forum = channel.parent
    available_tags = {tag.name: tag for tag in forum.available_tags}

    if TAG_ENDED not in available_tags:
        return None, TAG_ENDED

    new_tags = [tag for tag in channel.applied_tags if tag.name != TAG_ONGOING]
    if available_tags[TAG_ENDED] not in new_tags:
        new_tags.append(available_tags[TAG_ENDED])

    return new_tags, None


def record_post_end(user_id: int) -> tuple[int, int]:
    end_count = increment_end_count(user_id)
    balance = add_balance(user_id, END_REWARD_AMOUNT)
    return end_count, balance


def get_active_post_limit(member: discord.Member) -> int:
    if any(role.id == ROLE_MULTITASKER for role in member.roles):
        return POST_ACTIVE_LIMIT_MULTITASKER
    return POST_ACTIVE_LIMIT


def get_active_post_usage(user_id: int) -> int:
    ensure_user(user_id)
    return get_active_post_count(user_id)


def has_active_post_slot(member: discord.Member) -> bool:
    return get_active_post_usage(member.id) < get_active_post_limit(member)


def record_post_create(user_id: int) -> int:
    return increment_post_count(user_id)


def can_promote(member: discord.Member) -> bool:
    return any(role.id == ROLE_PROMOTER for role in member.roles)


def get_promote_limit(member: discord.Member) -> int:
    role_ids = {role.id for role in member.roles}
    if ROLE_PROMOTER in role_ids and ROLE_PROMOTER_ADVANCED in role_ids:
        return PROMOTE_ADVANCED_DAILY_LIMIT
    return PROMOTE_DAILY_LIMIT


def get_promote_usage(user_id: int) -> int:
    ensure_user(user_id)
    used, _ = get_promote_info(user_id)
    return used


def has_promote_remaining(member: discord.Member) -> bool:
    return get_promote_usage(member.id) < get_promote_limit(member)


def has_promote_cost(user_id: int) -> bool:
    ensure_user(user_id)
    return get_balance(user_id) >= PROMOTE_COST


def record_promote(user_id: int) -> tuple[int, int]:
    new_used = increment_promote(user_id)
    new_balance = deduct_balance(user_id, PROMOTE_COST)
    return new_used, new_balance
