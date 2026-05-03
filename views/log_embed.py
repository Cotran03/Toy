# ──────────────────────────────────────────────
#  views/log.py  |  로그 전용 Embed
# ──────────────────────────────────────────────
import discord
from datetime import datetime, timezone


def log_embed(user: discord.User | discord.Member, command_name: str, details: str = "") -> discord.Embed:
    """유저가 명령어를 실행했을 때의 로그 Embed."""
    embed = discord.Embed(
        title="📋 명령어 로그",
        color=0x5865F2,
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(name="사용자",   value=f"{user} (`{user.id}`)", inline=False)
    embed.add_field(name="명령어",   value=f"`{command_name}`",     inline=True)
    embed.add_field(name="세부사항", value=details or "없음",        inline=True)
    embed.set_thumbnail(url=user.display_avatar.url)
    return embed


def system_log_embed(title: str, details: str = "") -> discord.Embed:
    """특정 유저 없이 봇이 자동으로 수행한 동작의 로그 Embed."""
    embed = discord.Embed(
        title=f"⚙️ {title}",
        color=0x95A5A6,
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(name="세부사항", value=details or "없음", inline=False)
    embed.set_footer(text="시스템 자동 실행")
    return embed