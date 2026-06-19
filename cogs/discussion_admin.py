import discord
from discord import app_commands
from discord.ext import commands

from config import GUILD_ID, SYSTEM_ADMIN_ROLES, USER_ADMIN_ROLES
from db.database import (
    DISCUSSION_SETTING_DEFAULTS,
    delete_forum_exclusion_history,
    get_all_discussion_settings,
    get_excluded_forum_ids,
    reset_discussion_setting,
    set_discussion_setting,
    set_forum_excluded,
)
from services.post_service import (
    build_ended_tags,
    is_ended_post,
    is_forum_post_channel,
    record_post_close,
    set_user_post_counts,
)

from views.post_embed import abnomal_end_embed

from utils.app_permissions import any_role
from utils.interactions import send_ephemeral
from utils.operation_locks import get_operation_lock
from utils.send_log import send_log


MAX_DISCUSSION_LIMIT = 100
SETTING_LABELS = {
    "post_active_limit": "일반 사용자 동시 토론 제한",
    "post_active_limit_multitasker": "멀티태스커 동시 토론 제한",
    "promote_daily_limit": "일반 홍보 일일 제한",
    "promote_advanced_daily_limit": "홍보대사 일일 제한",
}
SETTING_CHOICES = [
    app_commands.Choice(name=label, value=key)
    for key, label in SETTING_LABELS.items()
]


class DiscussionAdmin(commands.Cog):
    discussion_settings = app_commands.Group(
        name="discussion-settings",
        description="토론 포럼과 횟수 제한 설정을 관리합니다.",
        guild_ids=[GUILD_ID],
    )
    discussion_moderation = app_commands.Group(
        name="discussion-moderation",
        description="토론 비정상 종료와 사용자 집계를 관리합니다.",
        guild_ids=[GUILD_ID],
    )

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _build_summary(self, guild: discord.Guild) -> str:
        settings = get_all_discussion_settings()
        lines = ["토론 설정"]
        for key, value in settings.items():
            default = DISCUSSION_SETTING_DEFAULTS[key]
            lines.append(f"- {SETTING_LABELS[key]}: {value}회 (기본값 {default}회)")

        lines.append("\n토론에서 제외된 포럼")
        excluded_forum_ids = sorted(get_excluded_forum_ids())
        visible_forums = []
        for forum_id in excluded_forum_ids:
            forum = guild.get_channel(forum_id)
            if forum is None:
                delete_forum_exclusion_history(forum_id)
                continue
            visible_forums.append(forum.mention)

        lines.extend(f"- {mention}" for mention in visible_forums)
        if not visible_forums:
            lines.append("- 없음")

        return "\n".join(lines)

    @discussion_settings.command(name="show", description="현재 토론 설정과 제외 포럼을 확인합니다.")
    @any_role(SYSTEM_ADMIN_ROLES)
    async def show(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        if guild is None:
            await send_ephemeral(interaction, "서버 정보를 가져올 수 없습니다.")
            return

        embed = discord.Embed(
            title="토론 관리 설정",
            description=self._build_summary(guild),
            color=0x5865F2,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        await send_log(self.bot, interaction.user, "/discussion-settings show", "토론 설정 조회")

    @discussion_settings.command(name="set", description="토론 또는 홍보 횟수 제한을 변경합니다.")
    @app_commands.describe(setting="변경할 제한 설정", value="새 제한 횟수")
    @app_commands.default_permissions(manage_channels=True)
    @app_commands.choices(setting=SETTING_CHOICES)
    @any_role(SYSTEM_ADMIN_ROLES)
    async def set_setting(
        self,
        interaction: discord.Interaction,
        setting: app_commands.Choice[str],
        value: app_commands.Range[int, 1, MAX_DISCUSSION_LIMIT],
    ) -> None:
        key = setting.value
        old_value = get_all_discussion_settings()[key]
        set_discussion_setting(key, value)
        await send_ephemeral(interaction, f"{SETTING_LABELS[key]}: {old_value}회 → {value}회")
        await send_log(
            self.bot,
            interaction.user,
            "/discussion-settings set",
            f"{key}: {old_value} -> {value}",
        )

    @discussion_settings.command(name="reset", description="토론 또는 홍보 횟수 제한을 기본값으로 복원합니다.")
    @app_commands.describe(setting="기본값으로 복원할 제한 설정")
    @app_commands.default_permissions(manage_channels=True)
    @app_commands.choices(setting=SETTING_CHOICES)
    @any_role(SYSTEM_ADMIN_ROLES)
    async def reset_setting(
        self,
        interaction: discord.Interaction,
        setting: app_commands.Choice[str],
    ) -> None:
        key = setting.value
        old_value = get_all_discussion_settings()[key]
        default_value = reset_discussion_setting(key)
        await send_ephemeral(interaction, f"{SETTING_LABELS[key]}: {old_value}회 → 기본값 {default_value}회")
        await send_log(
            self.bot,
            interaction.user,
            "/discussion-settings reset",
            f"{key}: {old_value} -> default {default_value}",
        )

    @discussion_settings.command(name="exclude-forum", description="새 포스트를 토론 집계에서 제외합니다.")
    @app_commands.describe(forum="토론에서 제외할 포럼")
    @app_commands.default_permissions(manage_channels=True)
    @any_role(SYSTEM_ADMIN_ROLES)
    async def exclude_forum(
        self,
        interaction: discord.Interaction,
        forum: discord.ForumChannel,
    ) -> None:
        changed = set_forum_excluded(forum.id, True)
        if not changed:
            await send_ephemeral(interaction, f"{forum.mention}은 이미 토론에서 제외되어 있습니다.")
            await send_log(
                self.bot,
                interaction.user,
                "/discussion-settings exclude-forum",
                f"이미 제외된 포럼: {forum.name} ({forum.id})",
            )
            return

        await send_ephemeral(
            interaction,
            f"{forum.mention}을 토론에서 제외했습니다.\n기존 포스트는 계속 토론으로 처리되고, 지금부터 생성되는 포스트만 제외됩니다.",
        )
        await send_log(self.bot, interaction.user, "/discussion-settings exclude-forum", f"{forum.name} ({forum.id})")

    @discussion_settings.command(name="include-forum", description="새 포스트를 토론 집계에 포함합니다.")
    @app_commands.describe(forum="토론에 포함할 포럼")
    @app_commands.default_permissions(manage_channels=True)
    @any_role(SYSTEM_ADMIN_ROLES)
    async def include_forum(
        self,
        interaction: discord.Interaction,
        forum: discord.ForumChannel,
    ) -> None:
        changed = set_forum_excluded(forum.id, False)
        if not changed:
            await send_ephemeral(interaction, f"{forum.mention}은 이미 토론에 포함되어 있습니다.")
            await send_log(
                self.bot,
                interaction.user,
                "/discussion-settings include-forum",
                f"이미 포함된 포럼: {forum.name} ({forum.id})",
            )
            return

        await send_ephemeral(
            interaction,
            f"{forum.mention}을 토론에 포함했습니다.\n지금부터 생성되는 포스트가 토론으로 집계됩니다.",
        )
        await send_log(self.bot, interaction.user, "/discussion-settings include-forum", f"{forum.name} ({forum.id})")

    async def _close_discussion(
        self,
        interaction: discord.Interaction,
        channel: discord.Thread,
        reason: str,
    ) -> None:
        if is_ended_post(channel):
            await send_ephemeral(interaction, "이미 종료된 토론입니다.")
            return

        new_tags, missing_tag = build_ended_tags(channel)
        if missing_tag:
            await send_ephemeral(interaction, f"`{missing_tag}` 태그를 찾을 수 없습니다.")
            return

        await interaction.response.defer(ephemeral=True)
        await channel.edit(applied_tags=new_tags, locked=True, archived=True, reason=reason)
        await channel.send(embed=abnomal_end_embed(reason))
        owner_id = channel.owner_id or interaction.user.id
        end_count = record_post_close(owner_id)
        await send_ephemeral(interaction, f"토론을 보상 없이 비정상 종료했습니다.\n종료한 토론 수: {end_count}")
        await send_log(
            self.bot,
            interaction.user,
            "/discussion-moderation close",
            f"포스트: {channel.name} / 소유자: {owner_id} / 사유: {reason}",
        )

    @discussion_moderation.command(name="close", description="현재 토론을 비정상 종료하고 보상을 지급하지 않습니다.")
    @app_commands.describe(reason="비정상 종료 사유")
    @app_commands.default_permissions(manage_messages=True)
    @any_role(USER_ADMIN_ROLES)
    async def close(self, interaction: discord.Interaction, reason: str) -> None:
        channel = interaction.channel
        if not isinstance(channel, discord.Thread) or not is_forum_post_channel(channel):
            await send_ephemeral(interaction, "집계 대상 토론 포스트 안에서만 사용할 수 있습니다.")
            return

        end_lock = get_operation_lock(self.bot, "discussion_end", channel.id)
        if end_lock.locked():
            await send_ephemeral(interaction, "이 토론은 이미 종료 처리 중입니다.")
            await send_log(self.bot, interaction.user, "/discussion-moderation close", f"동시 종료 시도 차단: {channel.name}")
            return

        async with end_lock:
            await self._close_discussion(interaction, channel, reason)

    @discussion_moderation.command(name="set-counts", description="사용자의 토론 집계 횟수를 정확한 값으로 보정합니다.")
    @app_commands.describe(member="보정할 사용자", post_count="게시한 토론 수", end_count="종료한 토론 수")
    @app_commands.default_permissions(manage_messages=True)
    @any_role(USER_ADMIN_ROLES)
    async def set_counts(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        post_count: app_commands.Range[int, 0, 1_000_000_000],
        end_count: app_commands.Range[int, 0, 1_000_000_000],
    ) -> None:
        if end_count > post_count:
            await send_ephemeral(interaction, "종료한 토론 수는 게시한 토론 수보다 많을 수 없습니다.")
            return

        stored_post_count, stored_end_count = set_user_post_counts(member.id, post_count, end_count)
        await send_ephemeral(
            interaction,
            f"{member.mention}의 토론 횟수를 보정했습니다.\n게시: {stored_post_count}회 / 종료: {stored_end_count}회",
        )
        await send_log(
            self.bot,
            interaction.user,
            "/discussion-moderation set-counts",
            f"대상: {member} / 게시: {stored_post_count} / 종료: {stored_end_count}",
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(DiscussionAdmin(bot))
