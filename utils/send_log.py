# ──────────────────────────────────────────────
#  util/send_log.py  |  로그 채널 전송 유틸
# ──────────────────────────────────────────────
# Import Config
from config import LOG_CHANNEL

# Import Views
from views.log_embed import log_embed, system_log_embed


async def send_log(bot, user, command_name: str, details: str = "") -> None:
    """유저 명령어 실행 로그. 모든 명령어에서 호출."""
    log_channel = bot.get_channel(LOG_CHANNEL)
    if log_channel:
        embed = log_embed(user, command_name, details)
        await log_channel.send(embed=embed)


async def send_system_log(bot, title: str, details: str = "") -> None:
    """봇 자동 동작 로그. 루프·스케줄러 등 유저 없는 동작에서 호출."""
    log_channel = bot.get_channel(LOG_CHANNEL)
    if log_channel:
        embed = system_log_embed(title, details)
        await log_channel.send(embed=embed)
