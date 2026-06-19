from datetime import datetime, timezone

import discord


def _display_name(user: discord.User | discord.Member) -> str:
    return getattr(user, "display_name", user.name)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def end_embed() -> discord.Embed:
    return discord.Embed(
        title="토론이 종료되었습니다",
        description=(
            "이번 토론이 각자의 생각을 정리하고 시야를 넓히는 계기가 되었기를 바랍니다.\n"
            "서로의 의견을 존중하며 더 깊은 고민으로 이어가길 기대합니다."
        ),
        color=0x95A5A6,
        timestamp=_now(),
    )

def abnomal_end_embed(description: str) -> discord.Embed:
    return discord.Embed(
        title="토론이 비정상적으로 종료되었습니다",
        description=(
            "이번 토론은 운영진에 의해 비정상적으로 종료되었습니다.\n"
            f"사유: {description}\n"
            "운영진의 결정에 따라 토론이 종료되었으며, 이에 대한 자세한 내용은 운영진에게 문의해주세요."
        ),
        color=0x95A5A6,
        timestamp=_now(),
    )


def promote_channel_embed(user: discord.Member, channel: discord.Thread) -> discord.Embed:
    embed = discord.Embed(
        title="토론 홍보",
        description=f"[**{channel.name}**]({channel.jump_url})\n\n제목을 눌러 토론으로 이동할 수 있습니다.",
        color=0xEB459E,
        timestamp=_now(),
    )
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.add_field(name="홍보자", value=_display_name(user), inline=True)
    embed.add_field(name="포스트", value=f"`{channel.name}`", inline=True)
    return embed


def promote_remaining_embed(used: int, limit: int) -> discord.Embed:
    remaining = max(limit - used, 0)
    return discord.Embed(
        title="홍보 완료",
        description=f"오늘 남은 홍보 횟수: **{remaining}회** / {limit}회",
        color=0xEB459E,
        timestamp=_now(),
    )


def not_forum_post_embed(
    title: str = "사용 불가",
    description: str = "이 명령어는 포럼 채널의 포스트 안에서만 사용할 수 있습니다.",
) -> discord.Embed:
    return discord.Embed(
        title=title,
        description=description,
        color=0xED4245,
        timestamp=_now(),
    )


def post_no_permission_embed(
    title: str = "권한 없음",
    description: str = "이 명령어를 사용할 권한이 없습니다.",
) -> discord.Embed:
    return discord.Embed(
        title=title,
        description=description,
        color=0xED4245,
        timestamp=_now(),
    )


def promote_limit_embed(limit: int) -> discord.Embed:
    return discord.Embed(
        title="홍보 횟수 초과",
        description=f"하루 최대 홍보 횟수인 **{limit}회**를 모두 사용했습니다.\n자정 이후 다시 시도해주세요.",
        color=0xED4245,
        timestamp=_now(),
    )


def promote_cost_embed(cost: int) -> discord.Embed:
    return discord.Embed(
        title="INS 부족",
        description=f"/promote 사용에는 {cost} INS가 필요합니다.",
        color=0xED4245,
        timestamp=_now(),
    )


def tag_not_found_embed(tag_name: str) -> discord.Embed:
    return discord.Embed(
        title="태그 오류",
        description=f"`{tag_name}` 태그를 포럼에서 찾을 수 없습니다.\n태그 이름을 확인해주세요.",
        color=0xED4245,
        timestamp=_now(),
    )
