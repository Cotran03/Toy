# ──────────────────────────────────────────────
#  cogs/post.py  |  포스트 관련 커맨드
# ──────────────────────────────────────────────
import discord
from discord import app_commands
from discord.ext import commands

from config import (
    GUILD_ID,
    PROMOTE_CHANNEL, PROMOTE_DAILY_LIMIT,
)
from services.post_service import (
    build_ended_tags,
    can_end_post,
    can_promote,
    has_promote_remaining,
    is_forum_post_channel,
    record_post_end,
    record_promote,
)
from utils.send_log import send_log
from views.post_embed import (
    end_embed,
    promote_channel_embed,
    promote_remaining_embed,
    not_forum_post_embed,
    no_permission_embed,
    promote_limit_embed,
    tag_not_found_embed,
)

GUILD = discord.Object(id=GUILD_ID)


def is_forum_post(interaction: discord.Interaction) -> bool:
    """포럼 채널의 스레드(포스트)인지 확인."""
    return is_forum_post_channel(interaction.channel)


class Post(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── Command: /end ────────────────────────────
    @app_commands.command(name="end", description="토론 포스트를 종료합니다.")
    @app_commands.guilds(GUILD)
    async def end(self, interaction: discord.Interaction):
        # 포럼 포스트 체크
        if not is_forum_post(interaction):
            await interaction.response.send_message(embed=not_forum_post_embed(), ephemeral=True)
            return

        channel = interaction.channel
        member  = interaction.user

        # 권한 체크: 포스트 게시자 또는 POST_END_ROLE 보유자
        if not can_end_post(member, channel):
            await interaction.response.send_message(embed=no_permission_embed(), ephemeral=True)
            await send_log(self.bot, member, "/end", f"권한 없는 사용자 사용 시도 — 포스트: '{channel.name}'")
            return

        # 태그 처리
        new_tags, missing_tag = build_ended_tags(channel)

        if missing_tag:
            await interaction.response.send_message(embed=tag_not_found_embed(missing_tag), ephemeral=True)
            return

        # '진행중' 제거 + '종료됨' 추가
        # 종료 메시지 전송 후 잠금
        await interaction.response.send_message(embed=end_embed())
        await channel.edit(applied_tags=new_tags, locked=True, archived=True)

        record_post_end(member.id)
        await send_log(self.bot, member, "/end", f"포스트 '{channel.name}' 종료")

    # ── Command: /promote ────────────────────────
    @app_commands.command(name="promote", description="현재 포스트를 홍보 채널에 홍보합니다.")
    @app_commands.guilds(GUILD)
    async def promote(self, interaction: discord.Interaction):
        # 포럼 포스트 체크
        if not is_forum_post(interaction):
            await interaction.response.send_message(embed=not_forum_post_embed(), ephemeral=True)
            return

        member = interaction.user

        # 역할 체크
        if not can_promote(member):
            await interaction.response.send_message(embed=no_permission_embed(), ephemeral=True)
            await send_log(self.bot, member, "/promote", "권한 없는 사용자 사용 시도")
            return

        # 하루 횟수 체크
        if not has_promote_remaining(member.id):
            await interaction.response.send_message(embed=promote_limit_embed(PROMOTE_DAILY_LIMIT), ephemeral=True)
            return

        # 홍보 채널에 embed 전송
        promote_ch = self.bot.get_channel(PROMOTE_CHANNEL)
        if promote_ch:
            await promote_ch.send(embed=promote_channel_embed(member, interaction.channel))

        # 횟수 증가
        new_used = record_promote(member.id)

        # 남은 횟수 안내 — defer 후 followup으로 전송, 10초 후 자동 삭제
        await interaction.response.defer(ephemeral=False)
        followup_msg = await interaction.followup.send(
            embed=promote_remaining_embed(new_used, PROMOTE_DAILY_LIMIT),
            wait=True,
        )
        await followup_msg.delete(delay=10)

        await send_log(
            self.bot, member, "/promote",
            f"포스트 '{interaction.channel.name}' 홍보 / 오늘 {new_used}/{PROMOTE_DAILY_LIMIT}회 사용"
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Post(bot))
