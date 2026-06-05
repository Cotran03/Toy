import discord

from config import BOT_COMMAND_CHANNEL, LOG_CHANNEL
from views.log_embed import log_embed, system_log_embed


async def _get_channel(bot, channel_id: int, label: str):
    channel = bot.get_channel(channel_id)
    if channel is not None:
        return channel

    try:
        return await bot.fetch_channel(channel_id)
    except (discord.Forbidden, discord.NotFound, discord.HTTPException) as exc:
        print(f"[{label}] 채널 조회 실패 ({channel_id}): {exc}")
        return None


async def _send_embed(bot, channel_id: int, embed: discord.Embed, label: str) -> None:
    channel = await _get_channel(bot, channel_id, label)
    if channel is None:
        return

    if not hasattr(channel, "send"):
        print(f"[{label}] 메시지를 보낼 수 없는 채널 타입입니다: {type(channel).__name__}")
        return

    try:
        await channel.send(embed=embed)
    except (discord.Forbidden, discord.HTTPException) as exc:
        print(f"[{label}] 전송 실패 ({channel_id}): {exc}")


async def send_log(bot, user, command_name: str, details: str = "") -> None:
    """Send command usage logs to LOG_CHANNEL."""
    embed = log_embed(user, command_name, details)
    await _send_embed(bot, LOG_CHANNEL, embed, "send_log")


async def send_system_log(bot, title: str, details: str = "") -> None:
    """Send automatic system logs to LOG_CHANNEL."""
    embed = system_log_embed(title, details)
    await _send_embed(bot, LOG_CHANNEL, embed, "send_system_log")


async def send_command_result(bot, title: str, details: str = "") -> None:
    """Send command output to BOT_COMMAND_CHANNEL."""
    embed = system_log_embed(title, details)
    await _send_embed(bot, BOT_COMMAND_CHANNEL, embed, "send_command_result")
