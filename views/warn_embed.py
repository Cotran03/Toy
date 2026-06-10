from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import discord


WARNING_TIMEZONE = ZoneInfo("Asia/Seoul")


def _display_name(user: discord.User | discord.Member) -> str:
    return getattr(user, "display_name", user.name)


def _now() -> datetime:
    return datetime.now(WARNING_TIMEZONE)


def _expiration_text(days: int) -> str:
    timestamp = int((_now() + timedelta(days=days)).timestamp())
    return f"<t:{timestamp}:F>\n<t:{timestamp}:R>"


def warn_notice_embed(
    member: discord.Member,
    added: int,
    total: int,
    reason: str,
    punishment: str,
    moderator: discord.Member,
) -> discord.Embed:
    embed = discord.Embed(
        title="경고 부여",
        color=0xFEE75C,
        timestamp=_now(),
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="대상", value=f"{member.mention}\n`{member.id}`", inline=False)
    embed.add_field(name="이번 경고 수", value=f"`{added}회`", inline=True)
    embed.add_field(name="누적 경고 수", value=f"`{total}회`", inline=True)
    embed.add_field(name="사유", value=reason, inline=False)
    embed.add_field(name="제재", value=f"`{punishment}`", inline=True)
    embed.add_field(name="처리자", value=moderator.display_name, inline=True)
    embed.add_field(name="경고 차감 예정", value=_expiration_text(30), inline=False)
    return embed


def warnoff_notice_embed(
    member: discord.User,
    total: int,
    moderator: discord.Member,
) -> discord.Embed:
    embed = discord.Embed(
        title="경고 차감",
        color=0x57F287,
        timestamp=_now(),
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="대상", value=_display_name(member), inline=False)
    embed.add_field(name="차감 수", value="`1회`", inline=True)
    embed.add_field(name="누적 경고 수", value=f"`{total}회`", inline=True)
    embed.add_field(name="처리자", value=moderator.display_name, inline=True)
    return embed


def warn_expire_notice_embed(user: discord.User | None, count: int, total: int) -> discord.Embed:
    user_value = _display_name(user) if user else "알 수 없음"
    embed = discord.Embed(
        title="경고 만료",
        description="30일 경과로 자동 차감되었습니다.",
        color=0x95A5A6,
        timestamp=_now(),
    )
    embed.add_field(name="대상", value=f"`{user_value}`", inline=False)
    embed.add_field(name="만료된 경고", value=f"`{count}회`", inline=True)
    embed.add_field(name="남은 경고 수", value=f"`{total}회`", inline=True)
    embed.set_footer(text="시스템 자동 처리")
    return embed
