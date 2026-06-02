from datetime import datetime, timezone

import discord


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _display_name(user: discord.User | discord.Member) -> str:
    return getattr(user, "display_name", user.name)


def _inquiry_mention(channel_id: int) -> str:
    return f"<#{channel_id}>" if channel_id > 0 else "문의사항 채널"


def secondary_warn_notice_embed(
    member: discord.Member,
    added: int,
    before: int,
    total: int,
    reason: str,
    punishment: str,
    role: discord.Role | None,
    moderator: discord.Member,
    inquiry_channel_id: int,
) -> discord.Embed:
    embed = discord.Embed(
        title="경고 기록",
        description=(
            f"유저: {member.mention}\n\n"
            f"사유: {reason}\n\n"
            f"지급 경고 갯수: {added}개\n\n"
            f"처벌 방식: {punishment}"
        ),
        color=0xFEE75C,
        timestamp=_now(),
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_footer(text=f"문의는 {_inquiry_mention(inquiry_channel_id)}으로..")
    return embed


def secondary_warnoff_notice_embed(
    user: discord.User | discord.Member,
    before: int,
    total: int,
    role: discord.Role | None,
    moderator: discord.Member,
) -> discord.Embed:
    embed = discord.Embed(
        title="경고 취소",
        description="두 번째 서버 경고 취소 안내입니다.",
        color=0x57F287,
        timestamp=_now(),
    )
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.add_field(name="대상", value=f"{user.mention}\n`{user.id}`", inline=False)
    embed.add_field(name="기존 경고", value=f"`{before}건`", inline=True)
    embed.add_field(name="누적 경고", value=f"`{total}건`", inline=True)
    embed.add_field(name="현재 경고 역할", value=role.mention if role else "`없음`", inline=True)
    embed.add_field(name="처리자", value=f"{moderator.mention}", inline=True)
    return embed


def secondary_warn_debug_embed(
    command_name: str,
    moderator: discord.User | discord.Member,
    target: discord.User | discord.Member,
    amount_text: str,
    before: int,
    total: int,
    reason: str,
    punishment: str,
    role: discord.Role | None,
    status: str,
) -> discord.Embed:
    embed = discord.Embed(
        title="경고 처리 로그",
        color=0x5865F2,
        timestamp=_now(),
    )
    embed.add_field(name="명령어", value=f"`/{command_name}`", inline=True)
    embed.add_field(name="처리자", value=f"{_display_name(moderator)}\n`{moderator.id}`", inline=True)
    embed.add_field(name="대상", value=f"{_display_name(target)}\n`{target.id}`", inline=True)
    embed.add_field(name="변경량", value=amount_text, inline=True)
    embed.add_field(name="경고 변화", value=f"`{before}건 -> {total}건`", inline=True)
    embed.add_field(name="경고 역할", value=role.mention if role else "`없음`", inline=True)
    embed.add_field(name="제재", value=f"`{punishment}`", inline=True)
    embed.add_field(name="상태", value=status, inline=False)
    embed.add_field(name="사유", value=reason or "`없음`", inline=False)
    return embed


def secondary_warn_expire_embed(user: discord.User | None, count: int, total: int) -> discord.Embed:
    user_value = _display_name(user) if user else "알 수 없음"
    embed = discord.Embed(
        title="경고 만료",
        description="기간 경과로 경고가 자동 삭제되었습니다.",
        color=0x95A5A6,
        timestamp=_now(),
    )
    embed.add_field(name="대상", value=f"`{user_value}`", inline=False)
    embed.add_field(name="만료된 경고", value=f"`{count}건`", inline=True)
    embed.add_field(name="남은 경고", value=f"`{total}건`", inline=True)
    return embed
