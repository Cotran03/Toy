from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands, tasks

from config import GUILD_ID, WARN_MAX, WARN_NOTICE_CHANNEL, WARN_ROLES, WARN_RULES
from db.database import (
    ensure_user,
    expire_old_warnings,
    get_economy_setting,
    get_warning_count,
    is_banned,
    record_warnings_and_penalty,
    remove_warning,
    set_banned,
)
from utils.app_permissions import any_role
from utils.activity_guard import is_restore_in_progress
from utils.interactions import send_ephemeral
from utils.punishments import adjusted_timeout_duration
from utils.send_log import send_log, send_system_log
from views.warn_embed import (
    warn_expire_notice_embed,
    warn_notice_embed,
    warnoff_notice_embed,
)


PUNISHMENT_BAN = "추방"
TIMEOUT_DURATION = {
    "타임아웃 12시간": timedelta(hours=12),
    "타임아웃 1일": timedelta(days=1),
    "타임아웃 3일": timedelta(days=3),
}


def parse_user_id(value: str) -> int | None:
    normalized = value.strip()
    if normalized.startswith("<@") and normalized.endswith(">"):
        normalized = normalized[2:-1]
        if normalized.startswith("!"):
            normalized = normalized[1:]

    if not normalized.isdecimal():
        return None

    user_id = int(normalized)
    return user_id if user_id > 0 else None


async def resolve_member(guild: discord.Guild, user: discord.User | discord.Member) -> discord.Member | None:
    if isinstance(user, discord.Member):
        return user

    member = guild.get_member(user.id)
    if member is not None:
        return member

    try:
        return await guild.fetch_member(user.id)
    except discord.NotFound:
        return None


async def apply_punishment(
    guild: discord.Guild,
    user: discord.User | discord.Member,
    punishment: str,
    reason: str,
) -> tuple[discord.Member | None, str | None]:
    if punishment in TIMEOUT_DURATION:
        member = await resolve_member(guild, user)
        if member is None:
            return None, "대상이 서버에 없어 타임아웃 제재는 적용하지 않고 경고만 기록했습니다."

        await member.timeout(TIMEOUT_DURATION[punishment], reason=reason)
        return member, None

    if punishment == PUNISHMENT_BAN:
        await guild.ban(user, reason=reason, delete_message_days=0)
        member = user if isinstance(user, discord.Member) else guild.get_member(user.id)
        return member, None

    member = user if isinstance(user, discord.Member) else guild.get_member(user.id)
    return member, None


def timeout_duration_for(total: int) -> timedelta | None:
    return TIMEOUT_DURATION.get(WARN_RULES.get(total, ""))


class Warn(commands.Cog):
    warn_admin = app_commands.Group(
        name="warn",
        description="사용자의 경고를 관리합니다.",
        guild_ids=[GUILD_ID],
        default_permissions=discord.Permissions(manage_messages=True),
    )

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.warning_expire_loop.start()

    def cog_unload(self) -> None:
        self.warning_expire_loop.cancel()

    def _notice_channel(self) -> discord.abc.Messageable | None:
        return self.bot.get_channel(WARN_NOTICE_CHANNEL)

    async def _send_notice(self, embed: discord.Embed, context: str) -> None:
        notice_channel = self._notice_channel()
        if notice_channel is None:
            await send_system_log(self.bot, "경고 공지 실패", f"{context} / 공지 채널을 찾을 수 없음")
            return

        try:
            await notice_channel.send(embed=embed)
        except (discord.Forbidden, discord.HTTPException) as exc:
            await send_system_log(self.bot, "경고 공지 실패", f"{context} / {exc}")

    @tasks.loop(hours=24)
    async def warning_expire_loop(self) -> None:
        if is_restore_in_progress(self.bot):
            return

        try:
            expired = expire_old_warnings()
            if not expired:
                return

            total_removed = sum(count for _, count in expired)

            for user_id, count in expired:
                remaining = get_warning_count(user_id)

                try:
                    user = await self.bot.fetch_user(user_id)
                except discord.NotFound:
                    user = None
                except discord.HTTPException as exc:
                    user = None
                    await send_system_log(self.bot, "경고 만료 처리 실패", f"사용자 조회 실패 / {user_id} / {exc}")

                await self._send_notice(
                    warn_expire_notice_embed(user, count, remaining),
                    f"경고 만료 공지 / 사용자 {user_id}",
                )

            await send_system_log(
                self.bot,
                "경고 만료 처리",
                f"총 {total_removed}건 자동 삭제 ({len(expired)}명)",
            )
        except Exception as exc:
            print(f"[경고 만료 루프 오류] {exc}")
            await send_system_log(self.bot, "경고 만료 처리 실패", str(exc))

    @warning_expire_loop.before_loop
    async def before_warning_expire_loop(self) -> None:
        await self.bot.wait_until_ready()

    @warn_admin.command(name="add", description="사용자에게 경고를 부여하고 제재를 적용합니다.")
    @app_commands.describe(member="경고를 부여할 사용자", count="부여할 경고 수", reason="경고 사유")
    @app_commands.default_permissions(manage_messages=True)
    @any_role(WARN_ROLES)
    async def warn(
        self,
        interaction: discord.Interaction,
        member: discord.User,
        count: app_commands.Range[int, 1, WARN_MAX],
        reason: str,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        await self._warn_user(interaction, member, count, reason, "/warn add")

    @warn_admin.command(name="add-id", description="서버를 나간 사용자에게 ID로 경고를 부여합니다.")
    @app_commands.describe(user_id="경고를 부여할 사용자의 Discord ID", count="부여할 경고 수", reason="경고 사유")
    @app_commands.default_permissions(manage_messages=True)
    @any_role(WARN_ROLES)
    async def warn_by_id(
        self,
        interaction: discord.Interaction,
        user_id: str,
        count: app_commands.Range[int, 1, WARN_MAX],
        reason: str,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        parsed_user_id = parse_user_id(user_id)
        if parsed_user_id is None:
            await send_ephemeral(interaction, "올바른 Discord 사용자 ID를 입력해주세요.")
            await send_log(self.bot, interaction.user, "/warn add-id", f"잘못된 사용자 ID 입력: {user_id}")
            return

        guild = interaction.guild
        if guild is None:
            await send_ephemeral(interaction, "서버 정보를 가져올 수 없습니다.")
            return

        member = guild.get_member(parsed_user_id)
        if member is not None:
            await self._warn_user(interaction, member, count, reason, "/warn add-id")
            return

        try:
            user = await self.bot.fetch_user(parsed_user_id)
        except discord.NotFound:
            await send_ephemeral(interaction, "해당 ID의 사용자를 찾을 수 없습니다. ID를 다시 확인해주세요.")
            await send_log(self.bot, interaction.user, "/warn add-id", f"사용자 조회 실패 / ID: {parsed_user_id}")
            return
        except discord.HTTPException as exc:
            await send_ephemeral(interaction, f"사용자 조회에 실패했습니다.\n오류: {exc}")
            await send_log(self.bot, interaction.user, "/warn add-id", f"사용자 조회 오류 / ID: {parsed_user_id} / {exc}")
            return

        await self._warn_user(interaction, user, count, reason, "/warn add-id")

    async def _warn_user(
        self,
        interaction: discord.Interaction,
        user: discord.User | discord.Member,
        count: int,
        reason: str,
        command_name: str,
    ) -> None:
        guild = interaction.guild
        if guild is None:
            await send_ephemeral(interaction, "서버 정보를 가져올 수 없습니다.")
            return

        ensure_user(user.id)

        current = get_warning_count(user.id)
        actual_add = min(count, WARN_MAX - current)
        if actual_add < 1:
            await send_ephemeral(interaction, f"{user.mention}님은 이미 최대 경고 수({WARN_MAX}회)에 도달했습니다.")
            await send_log(
                self.bot,
                interaction.user,
                command_name,
                f"'{user}' 이미 최대 경고 횟수({WARN_MAX}회) 도달",
            )
            return

        total = current + actual_add
        punishment = WARN_RULES.get(total, PUNISHMENT_BAN)
        try:
            member, punishment_note = await apply_punishment(guild, user, punishment, reason)
        except (discord.Forbidden, discord.HTTPException) as exc:
            await send_ephemeral(interaction, f"제재 적용에 실패하여 경고를 기록하지 않았습니다.\n오류: {exc}")
            await send_log(
                self.bot,
                interaction.user,
                command_name,
                f"제재 적용 실패 / 대상: {user} ({user.id}) / 예정 누적: {total} / {exc}",
            )
            return

        try:
            warn_penalty = get_economy_setting("warn_penalty")
            remaining_balance = record_warnings_and_penalty(
                user.id,
                actual_add,
                reason,
                warn_penalty,
                punishment == PUNISHMENT_BAN,
            )
        except Exception as exc:
            await send_ephemeral(interaction, "제재는 적용됐지만 경고 기록 또는 INS 차감에 실패했습니다.")
            await send_log(
                self.bot,
                interaction.user,
                command_name,
                f"제재 적용 후 DB 처리 실패 / 대상: {user} ({user.id}) / {exc}",
            )
            return

        notice_user = member or user
        await self._send_notice(
            warn_notice_embed(
                notice_user,
                actual_add,
                total,
                reason,
                punishment,
                interaction.user,
                punishment_note,
            ),
            f"경고 부여 공지 / 사용자 {user.id}",
        )

        note_text = f"\n주의: {punishment_note}" if punishment_note else ""
        await send_ephemeral(
            interaction,
            f"{user.mention}님에게 경고 {actual_add}회를 부여했습니다.\n누적 경고: {total}회 / 제재: {punishment}{note_text}",
        )
        await send_log(
            self.bot,
            interaction.user,
            command_name,
            (
                f"'{user}' ({user.id}) 경고 {actual_add}회 부여 / 누적 {total}회 / "
                f"사유: {reason} / 제재: {punishment} / 재화 -{warn_penalty} (잔액: {remaining_balance})"
            )
            + (f" / 주의: {punishment_note}" if punishment_note else ""),
        )

    @warn_admin.command(name="remove", description="사용자의 최근 경고 1회를 취소합니다.")
    @app_commands.describe(user="경고를 취소할 사용자")
    @app_commands.default_permissions(manage_messages=True)
    @any_role(WARN_ROLES)
    async def warnoff(self, interaction: discord.Interaction, user: discord.User) -> None:
        guild = interaction.guild
        if guild is None:
            await send_ephemeral(interaction, "서버 정보를 가져올 수 없습니다.")
            return

        await interaction.response.defer(ephemeral=True)
        ensure_user(user.id)

        current = get_warning_count(user.id)
        if current == 0:
            await send_ephemeral(interaction, f"{user.mention}님의 유효한 경고가 없습니다.")
            await send_log(self.bot, interaction.user, "/warn remove", f"'{user}' 유효한 경고 없음")
            return

        total = current - 1
        member = guild.get_member(user.id)
        adjustment_notes: list[str] = []

        try:
            if is_banned(user.id):
                await guild.unban(user, reason="경고 차감으로 인한 차단 해제")
                if timeout_duration_for(total) is not None:
                    adjustment_notes.append("차단 해제 후 대상이 서버 멤버가 아니므로 남은 단계의 타임아웃은 재입장 전 적용할 수 없습니다.")
            elif member is not None:
                previous_duration = timeout_duration_for(current)
                new_duration = timeout_duration_for(total)
                if new_duration is None:
                    await member.timeout(None, reason="경고 차감으로 인한 제재 갱신")
                else:
                    duration = (
                        adjusted_timeout_duration(member, previous_duration, new_duration)
                        if previous_duration is not None
                        else new_duration
                    )
                    await member.timeout(
                        duration if duration > timedelta(0) else None,
                        reason="경고 차감으로 인한 제재 갱신",
                    )
        except (discord.Forbidden, discord.NotFound, discord.HTTPException) as exc:
            await send_ephemeral(interaction, f"제재 조정에 실패하여 경고를 취소하지 않았습니다.\n오류: {exc}")
            await send_log(
                self.bot,
                interaction.user,
                "/warn remove",
                f"제재 조정 실패 / 대상: {user} ({user.id}) / {exc}",
            )
            return

        total = remove_warning(user.id)
        if is_banned(user.id) and total < WARN_MAX:
            set_banned(user.id, False)

        await self._send_notice(
            warnoff_notice_embed(user, total, interaction.user),
            f"경고 취소 공지 / 사용자 {user.id}",
        )

        note_text = f"\n주의: {' '.join(adjustment_notes)}" if adjustment_notes else ""
        await send_ephemeral(interaction, f"{user.mention}님의 최근 경고 1회를 취소했습니다.\n남은 경고: {total}회{note_text}")
        await send_log(
            self.bot,
            interaction.user,
            "/warn remove",
            f"'{user}' ({user.id}) 경고 1회 차감 / 누적 {total}회"
            + (f" / 주의: {' '.join(adjustment_notes)}" if adjustment_notes else ""),
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Warn(bot))
