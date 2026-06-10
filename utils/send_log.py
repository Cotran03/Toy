import discord

from config import LOG_CHANNEL, LOG_CHANNELS
from views.log_embed import log_embed, system_log_embed


LOG_CATEGORIES = frozenset(LOG_CHANNELS)
COMMAND_CATEGORY_PREFIXES = (
    (("/database",), "database"),
    (("/warn",), "warning"),
    (("/balance", "/store", "/reward", "/economy", "/seteconomy"), "economy"),
    (("/discussion", "/end", "/promote", "thread_create"), "discussion"),
    (("/verify",), "verify"),
    (("/cleanup", "/userinfo"), "admin"),
)
SYSTEM_CATEGORY_KEYWORDS = (
    (("DB", "데이터베이스", "백업", "복구"), "database"),
    (("경고", "제재"), "warning"),
    (("인증", "멤버 입장"), "verify"),
    (("경제", "INS", "상점"), "economy"),
    (("토론", "포스트", "홍보"), "discussion"),
)


def classify_command_log(command_name: str) -> str:
    for prefixes, category in COMMAND_CATEGORY_PREFIXES:
        if command_name.startswith(prefixes):
            return category
    return "command"


def classify_system_log(title: str) -> str:
    for keywords, category in SYSTEM_CATEGORY_KEYWORDS:
        if any(keyword in title for keyword in keywords):
            return category
    return "system"


def normalize_log_category(category: str, default: str) -> str:
    return category if category in LOG_CATEGORIES else default


def get_log_channel_id(category: str) -> int:
    category = normalize_log_category(category, "system")
    return LOG_CHANNELS[category] or LOG_CHANNEL


async def _get_channel(bot, channel_id: int, label: str):
    channel = bot.get_channel(channel_id)
    if channel is not None:
        return channel

    try:
        return await bot.fetch_channel(channel_id)
    except (discord.Forbidden, discord.NotFound, discord.HTTPException) as exc:
        print(f"[{label}] 채널 조회 실패 ({channel_id}): {exc}")
        return None


async def _send_embed(bot, channel_id: int, embed: discord.Embed, label: str) -> bool:
    channel = await _get_channel(bot, channel_id, label)
    if channel is None:
        return False

    if not hasattr(channel, "send"):
        print(f"[{label}] 메시지를 보낼 수 없는 채널 타입입니다: {type(channel).__name__}")
        return False

    try:
        await channel.send(embed=embed)
        return True
    except (discord.Forbidden, discord.HTTPException) as exc:
        print(f"[{label}] 전송 실패 ({channel_id}): {exc}")
        return False


async def _send_routed_embed(bot, category: str, embed: discord.Embed, label: str) -> None:
    channel_id = get_log_channel_id(category)
    if await _send_embed(bot, channel_id, embed, label):
        return

    if channel_id != LOG_CHANNEL:
        await _send_embed(bot, LOG_CHANNEL, embed, f"{label}:fallback")


async def send_log(
    bot,
    user,
    command_name: str,
    details: str = "",
    *,
    category: str | None = None,
) -> None:
    """Send a user or command log to its feature-specific channel."""
    category = normalize_log_category(category or classify_command_log(command_name), "command")
    embed = log_embed(user, command_name, details, category)
    await _send_routed_embed(bot, category, embed, f"send_log:{category}")


async def send_system_log(
    bot,
    title: str,
    details: str = "",
    *,
    category: str | None = None,
) -> None:
    """Send an automatic system log to its feature-specific channel."""
    category = normalize_log_category(category or classify_system_log(title), "system")
    embed = system_log_embed(title, details, category)
    await _send_routed_embed(bot, category, embed, f"send_system_log:{category}")
