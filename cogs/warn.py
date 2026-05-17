from datetime import timedelta

import discord
from discord.ext import commands, tasks

from config import WARN_MAX, WARN_NOTICE_CHANNEL, WARN_PENALTY, WARN_ROLES, WARN_RULES
from db.database import (
    add_warning,
    deduct_balance,
    ensure_user,
    expire_old_warnings,
    get_warning_count,
    is_banned,
    remove_warning,
    set_banned,
)
from utils.check_permission import has_any_role
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


async def apply_punishment(member: discord.Member, punishment: str, reason: str) -> None:
    if punishment in TIMEOUT_DURATION:
        await member.timeout(TIMEOUT_DURATION[punishment], reason=reason)
        return

    if punishment == PUNISHMENT_BAN:
        await member.ban(reason=reason, delete_message_days=0)


class Warn(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.warning_expire_loop.start()

    def cog_unload(self) -> None:
        self.warning_expire_loop.cancel()

    def _has_warn_permission(self, member: discord.Member) -> bool:
        return has_any_role(member, WARN_ROLES)

    async def _deny_without_permission(self, ctx: commands.Context, command_name: str) -> None:
        await ctx.message.delete()
        await send_log(self.bot, ctx.author, command_name, "권한 없는 사용자가 명령어 사용 시도")

    def _notice_channel(self) -> discord.abc.Messageable | None:
        return self.bot.get_channel(WARN_NOTICE_CHANNEL)

    @tasks.loop(hours=24)
    async def warning_expire_loop(self) -> None:
        try:
            expired = expire_old_warnings()
            if not expired:
                return

            notice_channel = self._notice_channel()
            total_removed = sum(count for _, count in expired)

            for user_id, count in expired:
                remaining = get_warning_count(user_id)
                if notice_channel is None:
                    continue

                try:
                    user = await self.bot.fetch_user(user_id)
                except discord.NotFound:
                    user = None

                await notice_channel.send(embed=warn_expire_notice_embed(user, count, remaining))

            await send_system_log(
                self.bot,
                "경고 만료 처리",
                f"총 {total_removed}건 자동 삭제 ({len(expired)}명)",
            )
        except Exception as exc:
            print(f"[경고 만료 루프 오류] {exc}")

    @warning_expire_loop.before_loop
    async def before_warning_expire_loop(self) -> None:
        await self.bot.wait_until_ready()

    @commands.command(name="warn")
    async def warn(
        self,
        ctx: commands.Context,
        member: discord.Member | None = None,
        count: int | None = None,
        *,
        reason: str | None = None,
    ) -> None:
        if not self._has_warn_permission(ctx.author):
            await self._deny_without_permission(ctx, "&warn")
            return

        if member is None or count is None or reason is None:
            await ctx.message.delete()
            await send_log(self.bot, ctx.author, "&warn", "인자 누락 — 사용법: &warn @멤버 [횟수] [사유]")
            return

        if count < 1:
            await ctx.message.delete()
            await send_log(self.bot, ctx.author, "&warn", "잘못된 횟수 입력 (1 이상이어야 함)")
            return

        ensure_user(member.id)

        current = get_warning_count(member.id)
        actual_add = min(count, WARN_MAX - current)
        if actual_add < 1:
            await ctx.message.delete()
            await send_log(self.bot, ctx.author, "&warn", f"'{member}' 이미 최대 경고 횟수({WARN_MAX}회) 도달")
            return

        for _ in range(actual_add):
            add_warning(member.id, reason)

        total = get_warning_count(member.id)
        punishment = WARN_RULES.get(total, PUNISHMENT_BAN)
        remaining_balance = deduct_balance(member.id, WARN_PENALTY)

        if punishment == PUNISHMENT_BAN:
            set_banned(member.id, True)

        await apply_punishment(member, punishment, reason)

        notice_channel = self._notice_channel()
        if notice_channel:
            await notice_channel.send(embed=warn_notice_embed(member, actual_add, total, reason, punishment, ctx.author))

        await ctx.message.delete()
        await send_log(
            self.bot,
            ctx.author,
            "&warn",
            (
                f"'{member}' ({member.id}) 경고 {actual_add}회 부여 / 누적 {total}회 / "
                f"사유: {reason} / 제재: {punishment} / 재화 -{WARN_PENALTY} (잔액: {remaining_balance})"
            ),
        )

    @warn.error
    async def warn_error(self, ctx: commands.Context, error: Exception) -> None:
        await ctx.message.delete()
        if isinstance(error, commands.MemberNotFound):
            await send_log(self.bot, ctx.author, "&warn", "존재하지 않는 멤버")
        elif isinstance(error, commands.BadArgument):
            await send_log(self.bot, ctx.author, "&warn", "잘못된 인자 형식 — 사용법: &warn @멤버 [횟수] [사유]")
        else:
            await send_log(self.bot, ctx.author, "&warn", f"예상치 못한 오류: {error}")
            print(f"[warn 오류] {error}")

    @commands.command(name="warnoff")
    async def warnoff(self, ctx: commands.Context, user: discord.User | None = None) -> None:
        if not self._has_warn_permission(ctx.author):
            await self._deny_without_permission(ctx, "&warnoff")
            return

        if user is None:
            await ctx.message.delete()
            await send_log(self.bot, ctx.author, "&warnoff", "인자 누락 — 사용법: &warnoff @멤버 or 유저ID")
            return

        ensure_user(user.id)

        current = get_warning_count(user.id)
        if current == 0:
            await ctx.message.delete()
            await send_log(self.bot, ctx.author, "&warnoff", f"'{user}' 유효한 경고 없음")
            return

        total = remove_warning(user.id)

        if is_banned(user.id):
            if total < WARN_MAX:
                try:
                    await ctx.guild.unban(user, reason="경고 차감으로 인한 차단 해제")
                    set_banned(user.id, False)
                except (discord.Forbidden, discord.NotFound, discord.HTTPException):
                    pass
        else:
            member = ctx.guild.get_member(user.id)
            if member:
                try:
                    await member.timeout(None)
                except (discord.Forbidden, discord.HTTPException):
                    pass

        notice_channel = self._notice_channel()
        if notice_channel:
            await notice_channel.send(embed=warnoff_notice_embed(user, total, ctx.author))

        await ctx.message.delete()
        await send_log(self.bot, ctx.author, "&warnoff", f"'{user}' ({user.id}) 경고 1회 차감 / 누적 {total}회")

    @warnoff.error
    async def warnoff_error(self, ctx: commands.Context, error: Exception) -> None:
        await ctx.message.delete()
        if isinstance(error, commands.UserNotFound):
            await send_log(self.bot, ctx.author, "&warnoff", "존재하지 않는 유저")
        elif isinstance(error, commands.BadArgument):
            await send_log(self.bot, ctx.author, "&warnoff", "잘못된 인자 형식 — 사용법: &warnoff @멤버 or 유저ID")
        else:
            await send_log(self.bot, ctx.author, "&warnoff", f"예상치 못한 오류: {error}")
            print(f"[warnoff 오류] {error}")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Warn(bot))
