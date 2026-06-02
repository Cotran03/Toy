from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands, tasks

from config.bot2 import (
    INQUIRY_CHANNEL,
    SECONDARY_GUILD_ID,
    WARN_ALLOW_ADMINISTRATOR,
    WARN_DEBUG_CHANNEL,
    WARN_EXPIRE_DAYS,
    WARN_MAX,
    WARN_NOTICE_CHANNEL,
    WARN_PERMISSION_ROLES,
    WARN_PUNISHMENTS,
    WARN_ROLE_BY_COUNT,
)
from db.secondary_warn import (
    add_secondary_warning,
    expire_secondary_warnings,
    get_secondary_warning_count,
    init_secondary_warn_db,
    remove_secondary_warning,
    set_secondary_banned,
)
from utils.check_permission import has_any_role
from views.secondary_warn_embed import (
    secondary_warn_debug_embed,
    secondary_warn_expire_embed,
    secondary_warn_notice_embed,
    secondary_warnoff_notice_embed,
)


SECONDARY_GUILD = discord.Object(id=SECONDARY_GUILD_ID)
NO_PUNISHMENT = "없음"


class SecondaryWarn(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        init_secondary_warn_db()
        self.secondary_warning_expire_loop.start()

    def cog_unload(self) -> None:
        self.secondary_warning_expire_loop.cancel()

    def _has_permission(self, member: discord.Member) -> bool:
        if WARN_ALLOW_ADMINISTRATOR and member.guild_permissions.administrator:
            return True
        return has_any_role(member, WARN_PERMISSION_ROLES)

    def _warning_role_ids(self) -> set[int]:
        return {role_id for role_id in WARN_ROLE_BY_COUNT.values() if role_id > 0}

    def _punishment_label(self, total: int) -> str:
        punishment = WARN_PUNISHMENTS.get(total, {})
        return str(punishment.get("label") or punishment.get("type") or NO_PUNISHMENT)

    def _notice_content(
        self,
        member: discord.Member,
        added: int,
        before: int,
        total: int,
        reason: str,
        punishment: str,
    ) -> str:
        return (
            f"{member.mention}님에게 경고가 부여되었습니다.\n"
            f"경고: {before}건 -> {total}건 (+{added}건)\n"
            f"제재: {punishment}\n"
            f"사유: {reason}"
        )

    def _warnoff_content(self, user: discord.User | discord.Member, before: int, total: int) -> str:
        return f"{user.mention}님의 경고가 취소되었습니다.\n경고: {before}건 -> {total}건 (-1건)"

    async def _send_channel_message(
        self,
        channel_id: int,
        *,
        content: str | None = None,
        embed: discord.Embed | None = None,
    ) -> None:
        if channel_id <= 0:
            return

        channel = self.bot.get_channel(channel_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except (discord.Forbidden, discord.NotFound, discord.HTTPException):
                return

        if hasattr(channel, "send"):
            await channel.send(content=content, embed=embed)

    async def _send_debug(
        self,
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
    ) -> None:
        await self._send_channel_message(
            WARN_DEBUG_CHANNEL,
            embed=secondary_warn_debug_embed(
                command_name,
                moderator,
                target,
                amount_text,
                before,
                total,
                reason,
                punishment,
                role,
                status,
            ),
        )

    async def _deny(self, interaction: discord.Interaction, command_name: str) -> None:
        await interaction.response.send_message("이 명령어를 사용할 권한이 없습니다.", ephemeral=True)
        await self._send_debug(
            command_name,
            interaction.user,
            interaction.user,
            "권한 없음",
            0,
            0,
            "",
            NO_PUNISHMENT,
            None,
            "권한 없는 사용자가 명령어 사용을 시도했습니다.",
        )

    async def _resolve_member(self, guild: discord.Guild, user_id: int) -> discord.Member | None:
        member = guild.get_member(user_id)
        if member is not None:
            return member

        try:
            return await guild.fetch_member(user_id)
        except (discord.NotFound, discord.HTTPException):
            return None

    async def _sync_warning_roles(self, member: discord.Member, total: int, reason: str) -> tuple[discord.Role | None, list[str]]:
        errors: list[str] = []
        warning_role_ids = self._warning_role_ids()
        target_role_id = WARN_ROLE_BY_COUNT.get(total, 0)
        target_role = member.guild.get_role(target_role_id) if target_role_id else None

        roles_to_remove = [
            role
            for role in member.roles
            if role.id in warning_role_ids and role.id != target_role_id
        ]
        if roles_to_remove:
            try:
                await member.remove_roles(*roles_to_remove, reason=reason)
            except (discord.Forbidden, discord.HTTPException) as exc:
                errors.append(f"경고 역할 제거 실패: {exc}")

        if target_role is not None and target_role not in member.roles:
            try:
                await member.add_roles(target_role, reason=reason)
            except (discord.Forbidden, discord.HTTPException) as exc:
                errors.append(f"경고 역할 부여 실패: {exc}")

        return target_role, errors

    async def _apply_punishment(self, member: discord.Member, total: int, reason: str) -> tuple[str, list[str]]:
        punishment = WARN_PUNISHMENTS.get(total, {})
        punishment_type = str(punishment.get("type", "none")).lower()
        label = self._punishment_label(total)
        errors: list[str] = []

        try:
            if punishment_type == "timeout":
                seconds = int(punishment.get("duration_seconds", 0))
                if seconds > 0:
                    await member.timeout(timedelta(seconds=seconds), reason=reason)
            elif punishment_type == "kick":
                await member.kick(reason=reason)
            elif punishment_type == "ban":
                await member.ban(reason=reason, delete_message_days=0)
                set_secondary_banned(member.id, True)
            elif punishment_type == "none":
                label = NO_PUNISHMENT if not punishment.get("label") else label
        except (discord.Forbidden, discord.HTTPException) as exc:
            errors.append(f"제재 적용 실패: {exc}")

        return label, errors

    async def _relax_punishment_after_cancel(
        self,
        guild: discord.Guild,
        user: discord.User,
        member: discord.Member | None,
        total: int,
    ) -> list[str]:
        errors: list[str] = []
        punishment_type = str(WARN_PUNISHMENTS.get(total, {}).get("type", "none")).lower()

        if punishment_type == "ban":
            set_secondary_banned(user.id, True)
            return errors

        if punishment_type != "ban":
            try:
                await guild.unban(user, reason="경고 취소로 인한 차단 해제 시도")
            except discord.NotFound:
                pass
            except (discord.Forbidden, discord.HTTPException) as exc:
                errors.append(f"차단 해제 실패: {exc}")

        if member is not None and punishment_type != "timeout":
            try:
                await member.timeout(None, reason="경고 취소로 인한 타임아웃 해제 시도")
            except (discord.Forbidden, discord.HTTPException) as exc:
                errors.append(f"타임아웃 해제 실패: {exc}")

        return errors

    @tasks.loop(hours=24)
    async def secondary_warning_expire_loop(self) -> None:
        expired = expire_secondary_warnings(WARN_EXPIRE_DAYS)
        if not expired:
            return

        guild = self.bot.get_guild(SECONDARY_GUILD_ID)
        for user_id, count in expired:
            total = get_secondary_warning_count(user_id, WARN_EXPIRE_DAYS)
            user = None
            try:
                user = await self.bot.fetch_user(user_id)
            except (discord.NotFound, discord.HTTPException):
                pass

            if guild is not None:
                member = await self._resolve_member(guild, user_id)
                if member is not None:
                    await self._sync_warning_roles(member, total, "경고 만료로 인한 역할 갱신")

            await self._send_channel_message(
                WARN_NOTICE_CHANNEL,
                embed=secondary_warn_expire_embed(user, count, total),
            )

    @secondary_warning_expire_loop.before_loop
    async def before_secondary_warning_expire_loop(self) -> None:
        await self.bot.wait_until_ready()

    @app_commands.command(name="경고", description="경고를 부여하고 누적 경고 수에 맞는 역할과 제재를 적용합니다.")
    @app_commands.guilds(SECONDARY_GUILD)
    @app_commands.describe(member="경고를 부여할 멤버", count="부여할 경고 수", reason="경고 사유")
    async def warn(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        count: app_commands.Range[int, 1, WARN_MAX],
        reason: str,
    ) -> None:
        if not isinstance(interaction.user, discord.Member) or not self._has_permission(interaction.user):
            await self._deny(interaction, "경고")
            return

        before = get_secondary_warning_count(member.id, WARN_EXPIRE_DAYS)
        actual_add = min(count, WARN_MAX - before)
        if actual_add < 1:
            await interaction.response.send_message(
                f"{member.mention}님은 이미 최대 경고 수({WARN_MAX}건)에 도달했습니다.",
                ephemeral=True,
            )
            await self._send_debug(
                "경고",
                interaction.user,
                member,
                "+0건",
                before,
                before,
                reason,
                self._punishment_label(before),
                None,
                "최대 경고 수에 도달해 추가하지 않았습니다.",
            )
            return

        for _ in range(actual_add):
            add_secondary_warning(member.id, reason, interaction.user.id, WARN_EXPIRE_DAYS)

        total = get_secondary_warning_count(member.id, WARN_EXPIRE_DAYS)
        role, role_errors = await self._sync_warning_roles(member, total, "경고 부여로 인한 역할 갱신")
        punishment, punishment_errors = await self._apply_punishment(member, total, reason)
        status = "\n".join(role_errors + punishment_errors) or "처리 완료"

        notice_embed = secondary_warn_notice_embed(
            member,
            actual_add,
            before,
            total,
            reason,
            punishment,
            role,
            interaction.user,
            INQUIRY_CHANNEL,
        )
        await interaction.response.send_message(embed=notice_embed, ephemeral=True)
        await self._send_channel_message(WARN_NOTICE_CHANNEL, embed=notice_embed)
        await self._send_debug(
            "경고",
            interaction.user,
            member,
            f"+{actual_add}건",
            before,
            total,
            reason,
            punishment,
            role,
            status,
        )

    @app_commands.command(name="경고취소", description="최근 경고 1건을 취소하고 경고 역할을 갱신합니다.")
    @app_commands.guilds(SECONDARY_GUILD)
    @app_commands.describe(user="경고를 취소할 사용자")
    async def warnoff(self, interaction: discord.Interaction, user: discord.User) -> None:
        if not isinstance(interaction.user, discord.Member) or not self._has_permission(interaction.user):
            await self._deny(interaction, "경고취소")
            return

        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("서버 정보를 가져올 수 없습니다.", ephemeral=True)
            return

        before = get_secondary_warning_count(user.id, WARN_EXPIRE_DAYS)
        if before == 0:
            await interaction.response.send_message(f"{user.mention}님의 유효한 경고가 없습니다.", ephemeral=True)
            await self._send_debug(
                "경고취소",
                interaction.user,
                user,
                "-0건",
                before,
                before,
                "",
                NO_PUNISHMENT,
                None,
                "취소할 경고가 없습니다.",
            )
            return

        total = remove_secondary_warning(user.id, WARN_EXPIRE_DAYS)
        member = await self._resolve_member(guild, user.id)
        role = None
        role_errors: list[str] = []
        if member is not None:
            role, role_errors = await self._sync_warning_roles(member, total, "경고 취소로 인한 역할 갱신")

        relax_errors = await self._relax_punishment_after_cancel(guild, user, member, total)
        if total < WARN_MAX and (member is not None or not relax_errors):
            set_secondary_banned(user.id, False)
        punishment = self._punishment_label(total) if total > 0 else NO_PUNISHMENT
        status = "\n".join(role_errors + relax_errors) or "처리 완료"

        notice_content = self._warnoff_content(user, before, total)
        notice_embed = secondary_warnoff_notice_embed(user, before, total, role, interaction.user)
        await interaction.response.send_message(embed=notice_embed, ephemeral=True)
        await self._send_channel_message(WARN_NOTICE_CHANNEL, content=notice_content, embed=notice_embed)
        await self._send_debug(
            "경고취소",
            interaction.user,
            user,
            "-1건",
            before,
            total,
            "",
            punishment,
            role,
            status,
        )


async def setup(bot: commands.Bot) -> None:
    if SECONDARY_GUILD_ID <= 0:
        print("[SecondaryWarn] SECONDARY_GUILD_ID is not set. Skipping cog.")
        return

    await bot.add_cog(SecondaryWarn(bot))
