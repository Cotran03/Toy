# Imports
import discord

# Import Config
from config import (
    GUILD_ID,
    POST_END_ROLES,
    ROLE_MULTITASKER,
    ROLE_PROMOTER,
    ROLE_PROMOTER_ADVANCED,
    TAG_ENDED,
    TAG_ONGOING,
)

# Import DB
from db.database import (
    complete_post_end,
    complete_promote,
    ensure_user,
    get_active_post_count,
    get_balance,
    get_discussion_setting,
    get_economy_setting,
    get_promote_info,
    increment_end_count,
    increment_post_count,
    is_forum_excluded_at,
    set_post_counts,
)


def get_end_reward_amount() -> int:
    return get_economy_setting("end_reward")


def get_promote_cost() -> int:
    return get_economy_setting("promote_cost")


def is_forum_post_channel(channel) -> bool:
    if (
        not isinstance(channel, discord.Thread)
        or not isinstance(channel.parent, discord.ForumChannel)
        or channel.guild.id != GUILD_ID
    ):
        return False

    created_at = int(channel.created_at.timestamp() * 1000)
    return not is_forum_excluded_at(channel.parent.id, created_at)


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


def is_ended_post(channel: discord.Thread) -> bool:
    return any(tag.name == TAG_ENDED for tag in channel.applied_tags)


def record_post_end(user_id: int) -> tuple[int, int]:
    return complete_post_end(user_id, get_end_reward_amount())


def record_post_close(user_id: int) -> int:
    return increment_end_count(user_id)


def get_active_post_limit(member: discord.Member) -> int:
    if any(role.id == ROLE_MULTITASKER for role in member.roles):
        return get_discussion_setting("post_active_limit_multitasker")
    return get_discussion_setting("post_active_limit")


def get_active_post_usage(user_id: int) -> int:
    ensure_user(user_id)
    return get_active_post_count(user_id)


def record_post_create(user_id: int) -> int:
    return increment_post_count(user_id)


def can_promote(member: discord.Member) -> bool:
    return any(role.id == ROLE_PROMOTER for role in member.roles)


def get_promote_limit(member: discord.Member) -> int:
    role_ids = {role.id for role in member.roles}
    if ROLE_PROMOTER in role_ids and ROLE_PROMOTER_ADVANCED in role_ids:
        return get_discussion_setting("promote_advanced_daily_limit")
    return get_discussion_setting("promote_daily_limit")


def get_promote_usage(user_id: int) -> int:
    ensure_user(user_id)
    used, _ = get_promote_info(user_id)
    return used


def has_promote_remaining(member: discord.Member) -> bool:
    return get_promote_usage(member.id) < get_promote_limit(member)


def has_promote_cost(user_id: int, cost: int | None = None) -> bool:
    ensure_user(user_id)
    return get_balance(user_id) >= (get_promote_cost() if cost is None else cost)


def record_promote(user_id: int, limit: int, cost: int | None = None) -> tuple[bool, str, int, int]:
    return complete_promote(user_id, get_promote_cost() if cost is None else cost, limit)


def set_user_post_counts(user_id: int, post_count: int, end_count: int) -> tuple[int, int]:
    return set_post_counts(user_id, post_count, end_count)
