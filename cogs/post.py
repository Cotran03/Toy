import asyncio
from collections import defaultdict

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
    is_ended_post,
    record_post_create,
    record_post_end,
    record_promote,
)
from utils.activity_guard import is_restore_in_progress
from utils.operation_locks import get_operation_lock
from utils.send_log import send_log, send_system_log
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
        self.promote_locks: defaultdict[int, asyncio.Lock] = defaultdict(asyncio.Lock)

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
        except discord.HTTPException as exc:
            await send_system_log(self.bot, "토론 처리 실패", f"포스트 소유자 조회 실패 / {thread.id} / {exc}")
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
        except (discord.Forbidden, discord.HTTPException) as exc:
            await send_system_log(self.bot, "토론 제한 처리 실패", f"삭제 안내 전송 실패 / {thread.id} / {exc}")

        try:
            await asyncio.sleep(OVER_LIMIT_THREAD_DELETE_DELAY)
            await thread.delete()
        except discord.Forbidden:
            try:
                await thread.edit(locked=True, archived=True)
            except (discord.Forbidden, discord.HTTPException) as exc:
                await send_system_log(self.bot, "토론 제한 처리 실패", f"포스트 잠금·보관 실패 / {thread.id} / {exc}")
        except discord.NotFound:
            await send_system_log(self.bot, "토론 제한 처리 실패", f"삭제 전에 포스트를 찾을 수 없음 / {thread.id}")

        await send_log(
            self.bot,
            member,
            "thread_create",
            f"진행 중 토론 제한 초과로 '{thread.name}' 삭제 ({active_count}/{active_limit})",
        )

    @commands.Cog.listener()
    async def on_thread_create(self, thread: discord.Thread) -> None:
        if is_restore_in_progress(self.bot):
            return

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

    async def _end_post(
        self,
        interaction: discord.Interaction,
        channel: discord.Thread,
        member: discord.Member,
    ) -> None:
        if is_ended_post(channel):
            await interaction.response.send_message("이미 종료된 토론입니다.", ephemeral=True)
            await send_log(self.bot, member, "/end", f"이미 종료된 포스트 재종료 시도: '{channel.name}'")
            return

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
            await send_log(self.bot, member, "/end", f"종료 태그 누락: {missing_tag} / 포스트: '{channel.name}'")
            return

        await interaction.response.defer(ephemeral=False)
        await channel.edit(applied_tags=new_tags, locked=True, archived=True)

        post_owner_id = channel.owner_id or member.id
        end_reward_amount = get_end_reward_amount()
        _, balance = record_post_end(post_owner_id)
        await interaction.edit_original_response(embed=end_embed())
        await send_log(
            self.bot,
            member,
            "/end",
            f"포스트 '{channel.name}' 종료 / 소유자 {post_owner_id} / 보상 {end_reward_amount} INS / 잔액 {balance} INS",
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
        end_lock = get_operation_lock(self.bot, "discussion_end", channel.id)
        if end_lock.locked():
            await interaction.response.send_message("이 토론은 이미 종료 처리 중입니다.", ephemeral=True)
            await send_log(self.bot, member, "/end", f"동시 종료 시도 차단: '{channel.name}'")
            return

        async with end_lock:
            await self._end_post(interaction, channel, member)

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

        promote_channel = self.bot.get_channel(PROMOTE_CHANNEL)
        if promote_channel is None or not hasattr(promote_channel, "send"):
            await interaction.response.send_message("홍보 채널을 찾을 수 없습니다.", ephemeral=True)
            await send_log(self.bot, member, "/promote", "홍보 실패 / 홍보 채널을 찾을 수 없음")
            return

        await interaction.response.defer(ephemeral=False)
        async with self.promote_locks[member.id]:
            promote_limit = get_promote_limit(member)
            if not has_promote_remaining(member):
                await interaction.followup.send(embed=promote_limit_embed(promote_limit), ephemeral=True)
                return

            promote_cost = get_promote_cost()
            if not has_promote_cost(member.id, promote_cost):
                await interaction.followup.send(embed=promote_cost_embed(promote_cost), ephemeral=True)
                return

            promote_mention = discord.Object(id=ROLE_PROMOTE_MENTION)
            try:
                promote_message = await promote_channel.send(
                    content=f"<@&{ROLE_PROMOTE_MENTION}>",
                    embed=promote_channel_embed(member, channel),
                    allowed_mentions=discord.AllowedMentions(
                        everyone=False,
                        users=False,
                        roles=[promote_mention],
                    ),
                )
            except (discord.Forbidden, discord.HTTPException) as exc:
                await interaction.followup.send("홍보 메시지 전송에 실패했습니다.", ephemeral=True)
                await send_log(self.bot, member, "/promote", f"홍보 메시지 전송 실패 / {exc}")
                return

            try:
                completed, reason, new_used, balance = record_promote(member.id, promote_limit, promote_cost)
            except Exception as exc:
                try:
                    await promote_message.delete()
                except (discord.Forbidden, discord.NotFound, discord.HTTPException) as delete_exc:
                    await send_log(
                        self.bot,
                        member,
                        "/promote",
                        f"DB 처리 실패 후 홍보 메시지 삭제 실패 / {delete_exc}",
                    )

                await interaction.followup.send(
                    "홍보 기록 처리에 실패해 게시된 홍보 메시지를 회수했습니다.",
                    ephemeral=True,
                )
                await send_log(self.bot, member, "/promote", f"홍보 게시 후 DB 처리 실패 / {exc}")
                return

            if not completed:
                try:
                    await promote_message.delete()
                except (discord.Forbidden, discord.NotFound, discord.HTTPException) as exc:
                    await send_log(self.bot, member, "/promote", f"결제 실패 홍보 메시지 삭제 실패 / {exc}")

                failure = "홍보 횟수가 모두 사용되었습니다." if reason == "limit" else "홍보 비용을 결제할 INS가 부족합니다."
                await interaction.followup.send(failure, ephemeral=True)
                await send_log(self.bot, member, "/promote", f"홍보 게시 후 결제 실패 / 사유: {reason}")
                return

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
