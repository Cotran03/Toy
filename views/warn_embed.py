# ──────────────────────────────────────────────
#  views/warn.py  |  cogs/warn.py 전용 Embed
# ──────────────────────────────────────────────
import discord
from datetime import datetime, timezone


def warn_notice_embed(
    member: discord.Member,
    added: int,
    total: int,
    reason: str,
    punishment: str,
    moderator: discord.Member,
) -> discord.Embed:
    """WARN_NOTICE_CHANNEL에 전송되는 경고 부여 공지 Embed."""
    embed = discord.Embed(
        title="⚠️ 경고 부여",
        color=0xFEE75C,
        timestamp=datetime.now(timezone.utc),
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="대상",           value=f"{member}",       inline=False)
    embed.add_field(name="이번 경고 횟수", value=f"`{added}회`",    inline=True)
    embed.add_field(name="누적 경고 횟수", value=f"`{total}회`",    inline=True)
    embed.add_field(name="사유",           value=reason,            inline=False)
    embed.add_field(name="제재",           value=f"`{punishment}`", inline=True)
    embed.add_field(name="처리자",         value=f"{moderator}",    inline=True)
    return embed


def warnoff_notice_embed(
    member: discord.Member,
    total: int,
    moderator: discord.Member,
) -> discord.Embed:
    """WARN_NOTICE_CHANNEL에 전송되는 경고 차감 공지 Embed."""
    embed = discord.Embed(
        title="✅ 경고 차감",
        color=0x57F287,
        timestamp=datetime.now(timezone.utc),
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="대상",           value=f"{member}",   inline=False)
    embed.add_field(name="차감 횟수",      value="`1회`",       inline=True)
    embed.add_field(name="누적 경고 횟수", value=f"`{total}회`",inline=True)
    embed.add_field(name="처리자",         value=f"{moderator}",inline=True)
    return embed


def warn_expire_notice_embed(user: discord.User | None, count: int, total: int) -> discord.Embed:
    """경고 만료 시 WARN_NOTICE_CHANNEL에 유저별로 전송되는 Embed."""
    user_value = str(user) if user else "알 수 없음"
    embed = discord.Embed(
        title="⏰ 경고 만료",
        description="30일 경과로 인한 자동 차감",
        color=0x95A5A6,
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(name="대상",           value=f"`{user_value}`", inline=False)
    embed.add_field(name="만료된 경고",    value=f"`{count}회`", inline=True)
    embed.add_field(name="남은 경고 횟수", value=f"`{total}회`", inline=True)
    embed.set_footer(text="시스템 자동 처리")
    return embed


def no_permission_embed() -> discord.Embed:
    return discord.Embed(
        title="⛔ 권한 없음",
        description="이 명령어를 사용할 권한이 없습니다.",
        color=0xED4245,
        timestamp=datetime.now(timezone.utc),
    )


def missing_arg_embed() -> discord.Embed:
    return discord.Embed(
        title="❌ 사용법 오류",
        description="사용법: `&warn @멤버 횟수 사유`",
        color=0xED4245,
        timestamp=datetime.now(timezone.utc),
    )


def member_not_found_embed() -> discord.Embed:
    return discord.Embed(
        title="❌ 오류",
        description="해당 멤버를 찾을 수 없습니다.",
        color=0xED4245,
        timestamp=datetime.now(timezone.utc),
    )


def invalid_count_embed() -> discord.Embed:
    return discord.Embed(
        title="❌ 오류",
        description="경고 횟수는 **1 이상의 정수**로 입력해주세요.",
        color=0xED4245,
        timestamp=datetime.now(timezone.utc),
    )


def no_warnings_embed() -> discord.Embed:
    return discord.Embed(
        title="❌ 오류",
        description="해당 유저의 유효한 경고가 없습니다.",
        color=0xED4245,
        timestamp=datetime.now(timezone.utc),
    )