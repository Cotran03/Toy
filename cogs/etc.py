from datetime import datetime
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands

from config import ADMIN_INFO_ROLES, CLEAR_ROLES, GUILD_ID, ROLE_INFO_ADVANCED
from db.database import (
    ensure_user,
    get_active_post_count,
    get_balance,
    get_end_count,
    get_last_reward_date,
    get_post_count,
    get_reward_streak,
    get_total_promote_count,
    get_warning_count,
)
from utils.app_permissions import any_role
from utils.interactions import send_ephemeral
from utils.send_log import send_log
from views.etc_embed import info_embed


GUILD = discord.Object(id=GUILD_ID)
CLEAR_LIMIT = 100
INFO_TIMEZONE = ZoneInfo("Asia/Seoul")


class Etc(commands.Cog):
    cleanup_admin = app_commands.Group(
        name="cleanup",
        description="채널 메시지를 관리합니다.",
        guild_ids=[GUILD_ID],
    )
    info_admin = app_commands.Group(
        name="userinfo",
        description="사용자의 상세 서버 정보를 확인합니다.",
        guild_ids=[GUILD_ID],
    )

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _has_info_advanced_role(self, member: discord.Member) -> bool:
        return any(role.id == ROLE_INFO_ADVANCED for role in member.roles)

    def _build_join_info(self, member: discord.Member) -> tuple[str, str]:
        joined_at = getattr(member, "joined_at", None)
        if joined_at is None:
            return "알 수 없음", "알 수 없음"

        joined_at = joined_at.replace(tzinfo=INFO_TIMEZONE) if joined_at.tzinfo is None else joined_at.astimezone(INFO_TIMEZONE)
        now = datetime.now(INFO_TIMEZONE)
        elapsed = now - joined_at
        days = elapsed.days
        hours = elapsed.seconds // 3600

        return joined_at.strftime("%Y-%m-%d %H:%M:%S"), f"{days}일 {hours}시간"

    def _build_info_data(self, member: discord.Member, *, advanced: bool | None = None) -> dict:
        ensure_user(member.id)
        joined_text, elapsed_text = self._build_join_info(member)
        return {
            "joined_text": joined_text,
            "elapsed_text": elapsed_text,
            "is_advanced": self._has_info_advanced_role(member) if advanced is None else advanced,
            "post_count": get_post_count(member.id),
            "end_count": get_end_count(member.id),
            "active_post_count": get_active_post_count(member.id),
            "total_promote_count": get_total_promote_count(member.id),
            "warning_count": get_warning_count(member.id),
            "balance": get_balance(member.id),
            "reward_streak": get_reward_streak(member.id),
            "last_reward_date": get_last_reward_date(member.id),
        }

    @cleanup_admin.command(name="clear", description="현재 채널의 최근 메시지를 삭제합니다.")
    @app_commands.describe(amount="삭제할 메시지 수")
    @app_commands.default_permissions(mention_everyone=True)
    @any_role(CLEAR_ROLES)
    async def clear(
        self,
        interaction: discord.Interaction,
        amount: app_commands.Range[int, 1, CLEAR_LIMIT],
    ) -> None:
        channel = interaction.channel
        if channel is None or not hasattr(channel, "purge"):
            await send_ephemeral(interaction, "이 채널에서는 메시지를 삭제할 수 없습니다.")
            await send_log(
                self.bot,
                interaction.user,
                "/cleanup clear",
                "메시지를 삭제할 수 없는 채널에서 사용 시도",
            )
            return

        await interaction.response.defer(ephemeral=True)
        deleted = await channel.purge(limit=amount)
        channel_name = getattr(channel, "name", "현재 채널")
        await send_ephemeral(interaction, f"#{channel_name}에서 {len(deleted)}개 메시지를 삭제했습니다.")
        await send_log(
            self.bot,
            interaction.user,
            "/cleanup clear",
            f"#{channel_name}에서 {len(deleted)}개 메시지 삭제",
        )

    @app_commands.command(name="ping", description="봇의 응답 속도를 확인합니다.")
    @app_commands.guilds(GUILD)
    async def ping(self, interaction: discord.Interaction) -> None:
        latency = self.bot.latency * 1000
        await interaction.response.send_message(
            f"Pong! {latency:.2f}ms",
            ephemeral=False,
            delete_after=5,
        )
        await send_log(self.bot, interaction.user, "/ping", f"봇 응답 속도 확인 - {latency:.2f}ms")

    @app_commands.command(name="info", description="본인의 서버 정보를 확인합니다.")
    @app_commands.describe(보이기="다른 사용자에게도 보이게 할지 선택합니다.")
    @app_commands.guilds(GUILD)
    async def info(self, interaction: discord.Interaction, 보이기: bool = False) -> None:
        member = interaction.user
        info_data = self._build_info_data(member)

        await interaction.response.send_message(embed=info_embed(member, info_data), ephemeral=not 보이기)
        await send_log(self.bot, member, "/info", "개인 정보 조회")

    @info_admin.command(name="member", description="사용자의 상세 서버 정보를 확인합니다.")
    @app_commands.describe(member="조회할 사용자")
    @app_commands.default_permissions(manage_messages=True)
    @any_role(ADMIN_INFO_ROLES)
    async def admin_info(self, interaction: discord.Interaction, member: discord.Member) -> None:
        await interaction.response.send_message(
            embed=info_embed(member, self._build_info_data(member, advanced=True)),
            ephemeral=True,
        )
        await send_log(self.bot, interaction.user, "/userinfo member", f"대상: {member}")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Etc(bot))
