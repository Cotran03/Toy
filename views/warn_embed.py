from datetime import datetime, timezone

import discord


def _display_name(user: discord.User | discord.Member) -> str:
    return getattr(user, "display_name", user.name)


def _now() -> datetime:
    return datetime.now(timezone.utc)


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
    embed.add_field(name="대상", value=member.display_name, inline=False)
    embed.add_field(name="이번 경고 수", value=f"`{added}회`", inline=True)
    embed.add_field(name="누적 경고 수", value=f"`{total}회`", inline=True)
    embed.add_field(name="사유", value=reason, inline=False)
    embed.add_field(name="제재", value=f"`{punishment}`", inline=True)
    embed.add_field(name="처리자", value=moderator.display_name, inline=True)
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


def warn_no_permission_embed(
    title: str = "권한 없음",
    description: str = "이 명령어를 사용할 권한이 없습니다.",
) -> discord.Embed:
    return discord.Embed(
        title=title,
        description=description,
        color=0xED4245,
        timestamp=_now(),
    )


def missing_arg_embed(
    title: str = "사용법 오류",
    description: str = "사용법: `&warn @멤버 횟수 사유`",
) -> discord.Embed:
    return discord.Embed(
        title=title,
        description=description,
        color=0xED4245,
        timestamp=_now(),
    )


def member_not_found_embed(
    title: str = "오류",
    description: str = "해당 멤버를 찾을 수 없습니다.",
) -> discord.Embed:
    return discord.Embed(
        title=title,
        description=description,
        color=0xED4245,
        timestamp=_now(),
    )


def invalid_count_embed(
    title: str = "오류",
    description: str = "경고 횟수는 **1 이상의 정수**로 입력해주세요.",
) -> discord.Embed:
    return discord.Embed(
        title=title,
        description=description,
        color=0xED4245,
        timestamp=_now(),
    )


def no_warnings_embed(
    title: str = "오류",
    description: str = "해당 유저에게 유효한 경고가 없습니다.",
) -> discord.Embed:
    return discord.Embed(
        title=title,
        description=description,
        color=0xED4245,
        timestamp=_now(),
    )
