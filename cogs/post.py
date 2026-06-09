import asyncio

import discord
from discord import app_commands
from discord.ext import commands

from config import GUILD_ID, PROMOTE_CHANNEL, ROLE_PROMOTE_MENTION
from services.post_service import (
    build_ended_tags,
    can_end_post,
    can_promote,
    get_active_post_limit,
    get_active_post_usage,
    get_end_reward_amount,
    get_promote_cost,
    get_promote_limit,
    has_promote_cost,
    has_promote_remaining,
    is_forum_post_channel,
    record_post_create,
    record_post_end,
    record_promote,
)
from utils.send_log import send_log
from views.post_embed import (
    end_embed,
    not_forum_post_embed,
    post_no_permission_embed,
    promote_channel_embed,
    promote_cost_embed,
    promote_limit_embed,
    promote_remaining_embed,
    tag_not_found_embed,
)


GUILD = discord.Object(id=GUILD_ID)
PROMOTE_RESULT_DELETE_DELAY = 10
OVER_LIMIT_THREAD_DELETE_DELAY = 10


def is_forum_post(interaction: discord.Interaction) -> bool:
    return is_forum_post_channel(interaction.channel)


class Post(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _fetch_thread_owner(self, thread: discord.Thread) -> discord.Member | None:
        if thread.owner_id is None:
            return None

        member = thread.guild.get_member(thread.owner_id)
        if member is not None:
            return member

        try:
            return await thread.guild.fetch_member(thread.owner_id)
        except discord.NotFound:
            return None

    async def _close_over_limit_thread(
        self,
        thread: discord.Thread,
        member: discord.Member,
        active_count: int,
        active_limit: int,
    ) -> None:
        try:
            await thread.send(
                f"진행 중인 토론은 최대 {active_limit}개까지 만들 수 있습니다. "
                "진행 중인 토론에서 /end를 사용한 뒤 새로 만들어주세요. "
                f"이 토론은 {OVER_LIMIT_THREAD_DELETE_DELAY}초 뒤 삭제됩니다."
            )
        except discord.Forbidden:
            pass

        try:
            await asyncio.sleep(OVER_LIMIT_THREAD_DELETE_DELAY)
            await thread.delete()
        except discord.Forbidden:
            try:
                await thread.edit(locked=True, archived=True)
            except discord.Forbidden:
                pass
        except discord.NotFound:
            pass

        await send_log(
            self.bot,
            member,
            "thread_create",
            f"진행 중 토론 제한 초과로 '{thread.name}' 삭제 ({active_count}/{active_limit})",
        )

    @commands.Cog.listener()
    async def on_thread_create(self, thread: discord.Thread) -> None:
        if not is_forum_post_channel(thread):
            return

        member = await self._fetch_thread_owner(thread)
        if member is None:
            return

        active_count = get_active_post_usage(member.id)
        active_limit = get_active_post_limit(member)
        if active_count >= active_limit:
            await self._close_over_limit_thread(thread, member, active_count, active_limit)
            return

        new_count = record_post_create(member.id)
        await send_log(
            self.bot,
            member,
            "thread_create",
            f"토론 '{thread.name}' 생성 / 게시한 토론 수 {new_count}",
        )

    @app_commands.command(name="end", description="토론 포스트를 종료합니다.")
    @app_commands.guilds(GUILD)
    async def end(self, interaction: discord.Interaction) -> None:
        if not is_forum_post(interaction):
            await interaction.response.send_message(
                embed=not_forum_post_embed(
                    description="/end는 포럼 채널의 포스트 안에서만 사용할 수 있습니다.",
                ),
                ephemeral=True,
            )
            return

        channel = interaction.channel
        member = interaction.user

        if not can_end_post(member, channel):
            await interaction.response.send_message(
                embed=post_no_permission_embed(
                    description="이 포스트를 종료할 권한이 없습니다.\n포스트 작성자 또는 종료 권한이 있는 역할만 사용할 수 있습니다.",
                ),
                ephemeral=True,
            )
            await send_log(self.bot, member, "/end", f"권한 없는 사용자 사용 시도 — 포스트: '{channel.name}'")
            return

        new_tags, missing_tag = build_ended_tags(channel)
        if missing_tag:
            await interaction.response.send_message(embed=tag_not_found_embed(missing_tag), ephemeral=True)
            return

        await interaction.response.send_message(embed=end_embed())
        await channel.edit(applied_tags=new_tags, locked=True, archived=True)

        post_owner_id = channel.owner_id or member.id
        end_reward_amount = get_end_reward_amount()
        _, balance = record_post_end(post_owner_id)
        await send_log(
            self.bot,
            member,
            "/end",
            f"포스트 '{channel.name}' 종료 / 소유자 {post_owner_id} / 보상 {end_reward_amount} INS / 잔액 {balance} INS",
        )

    @app_commands.command(name="promote", description="현재 포스트를 홍보 채널에 홍보합니다.")
    @app_commands.guilds(GUILD)
    async def promote(self, interaction: discord.Interaction) -> None:
        if not is_forum_post(interaction):
            await interaction.response.send_message(
                embed=not_forum_post_embed(
                    description="/promote는 포럼 채널의 포스트 안에서만 사용할 수 있습니다.",
                ),
                ephemeral=True,
            )
            return

        member = interaction.user
        channel = interaction.channel

        if not can_promote(member):
            await interaction.response.send_message(
                embed=post_no_permission_embed(
                    description="이 포스트를 홍보할 권한이 없습니다.\n홍보자 혹은 홍보대사 역할이 있는 사용자만 사용할 수 있습니다.",
                ),
                ephemeral=True,
            )
            await send_log(self.bot, member, "/promote", "권한 없는 사용자 사용 시도")
            return

        promote_limit = get_promote_limit(member)
        if not has_promote_remaining(member):
            await interaction.response.send_message(embed=promote_limit_embed(promote_limit), ephemeral=True)
            return

        promote_cost = get_promote_cost()
        if not has_promote_cost(member.id, promote_cost):
            await interaction.response.send_message(embed=promote_cost_embed(promote_cost), ephemeral=True)
            return

        promote_channel = self.bot.get_channel(PROMOTE_CHANNEL)
        if promote_channel:
            promote_mention = discord.Object(id=ROLE_PROMOTE_MENTION)
            await promote_channel.send(
                content=f"<@&{ROLE_PROMOTE_MENTION}>",
                embed=promote_channel_embed(member, channel),
                allowed_mentions=discord.AllowedMentions(
                    everyone=False,
                    users=False,
                    roles=[promote_mention],
                ),
            )

        new_used, balance = record_promote(member.id, promote_cost)

        await interaction.response.defer(ephemeral=False)
        followup_msg = await interaction.followup.send(
            embed=promote_remaining_embed(new_used, promote_limit),
            wait=True,
        )
        await followup_msg.delete(delay=PROMOTE_RESULT_DELETE_DELAY)

        await send_log(
            self.bot,
            member,
            "/promote",
            f"포스트 '{channel.name}' 홍보 / {promote_cost} INS 사용 / 잔액 {balance} INS / 오늘 {new_used}/{promote_limit}회 사용",
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Post(bot))
