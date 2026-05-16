# ──────────────────────────────────────────────
#  views/post_embed.py  |  cogs/post.py 전용 Embed
# ──────────────────────────────────────────────
# Imports
from datetime import datetime, timezone

import discord


def end_embed() -> discord.Embed:
    """포스트 종료 시 전송되는 Embed."""
    embed = discord.Embed(
        title="🔒 토론이 종료되었습니다",
        description="이번 토론이 각자의 생각을 정리하고 시야를 넓히는 계기가 되었기를 바랍니다.\n서로의 의견을 존중하며 더 깊은 고민으로 이어가길 기대합니다.",
        color=0x95A5A6,
        timestamp=datetime.now(timezone.utc),
    )
    return embed


def promote_channel_embed(user: discord.Member, channel: discord.Thread) -> discord.Embed:
    """PROMOTE_CHANNEL에 전송되는 홍보 Embed."""
    embed = discord.Embed(
        title="📢 토론 홍보",
        description=f"[**{channel.name}**]({channel.jump_url})\n\n포스트로 이동하려면 제목을 클릭하세요.",
        color=0xEB459E,
        timestamp=datetime.now(timezone.utc),
    )
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.add_field(name="홍보자",   value=f"{user}", inline=True)
    embed.add_field(name="포스트",   value=f"`{channel.name}`",     inline=True)
    return embed


def promote_remaining_embed(used: int, limit: int) -> discord.Embed:
    """홍보 사용자에게만 보이는 남은 횟수 안내 Embed."""
    remaining = limit - used
    embed = discord.Embed(
        title="📢 홍보 완료",
        description=f"오늘 남은 홍보 횟수: **{remaining}회** / {limit}회",
        color=0xEB459E,
        timestamp=datetime.now(timezone.utc),
    )
    return embed


def not_forum_post_embed() -> discord.Embed:
    """포럼 포스트가 아닌 곳에서 사용 시 안내 Embed."""
    return discord.Embed(
        title="❌ 사용 불가",
        description="이 명령어는 **포럼 채널의 포스트**에서만 사용할 수 있습니다.",
        color=0xED4245,
        timestamp=datetime.now(timezone.utc),
    )


def no_permission_embed() -> discord.Embed:
    return discord.Embed(
        title="⛔ 권한 없음",
        description="이 명령어를 사용할 권한이 없습니다.",
        color=0xED4245,
        timestamp=datetime.now(timezone.utc),
    )


def promote_limit_embed(limit: int) -> discord.Embed:
    """하루 홍보 횟수 초과 시 안내 Embed."""
    return discord.Embed(
        title="❌ 홍보 횟수 초과",
        description=f"하루 최대 홍보 횟수(**{limit}회**)를 모두 사용했습니다.\n자정 이후에 다시 시도해주세요.",
        color=0xED4245,
        timestamp=datetime.now(timezone.utc),
    )


def tag_not_found_embed(tag_name: str) -> discord.Embed:
    return discord.Embed(
        title="❌ 태그 오류",
        description=f"`{tag_name}` 태그를 포럼에서 찾을 수 없습니다.\n태그 이름을 확인해주세요.",
        color=0xED4245,
        timestamp=datetime.now(timezone.utc),
    )
