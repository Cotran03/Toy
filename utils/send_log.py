# ──────────────────────────────────────────────
#  util/send_log.py  |  로그 채널 전송 유틸
# ──────────────────────────────────────────────
# Import Config
import discord

from config import LOG_CHANNEL

# Import Views
from views.log_embed import log_embed, system_log_embed


async def _get_log_channel(bot):
    log_channel = bot.get_channel(LOG_CHANNEL)
    if log_channel is not None:
        return log_channel

    try:
        return await bot.fetch_channel(LOG_CHANNEL)
    except (discord.Forbidden, discord.NotFound, discord.HTTPException) as exc:
        print(f"[send_log] 로그 채널 조회 실패 ({LOG_CHANNEL}): {exc}")
        return None


async def _send_embed(bot, embed: discord.Embed) -> None:
    log_channel = await _get_log_channel(bot)
    if log_channel is None:
        return

    if not hasattr(log_channel, "send"):
        print(f"[send_log] 로그 채널이 메시지를 보낼 수 없는 타입입니다: {type(log_channel).__name__}")
        return

    try:
        await log_channel.send(embed=embed)
    except (discord.Forbidden, discord.HTTPException) as exc:
        print(f"[send_log] 로그 전송 실패 ({LOG_CHANNEL}): {exc}")


async def send_log(bot, user, command_name: str, details: str = "") -> None:
    """유저 명령어 실행 로그. 모든 명령어에서 호출."""
    embed = log_embed(user, command_name, details)
    await _send_embed(bot, embed)


async def send_system_log(bot, title: str, details: str = "") -> None:
    """봇 자동 동작 로그. 루프·스케줄러 등 유저 없는 동작에서 호출."""
    embed = system_log_embed(title, details)
    await _send_embed(bot, embed)
