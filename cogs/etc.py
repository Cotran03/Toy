from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

from config import GUILD_ID, ROLE_INFO_ADVANCED
from db.database import (
    ensure_user,
    get_active_post_count,
    get_balance,
    get_end_count,
    get_post_count,
    get_total_promote_count,
    get_warning_count,
)
from utils.send_log import send_log
from views.etc_embed import info_embed


GUILD = discord.Object(id=GUILD_ID)
CLEAR_LIMIT = 100


class Etc(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _has_info_advanced_role(self, member: discord.Member) -> bool:
        return any(role.id == ROLE_INFO_ADVANCED for role in member.roles)

    def _build_join_info(self, member: discord.Member) -> tuple[str, str]:
        joined_at = getattr(member, "joined_at", None)
        if joined_at is None:
            return "알 수 없음", "알 수 없음"

        now = datetime.now(tz=joined_at.tzinfo) if joined_at.tzinfo else datetime.utcnow()
        elapsed = now - joined_at
        days = elapsed.days
        hours = elapsed.seconds // 3600

        return joined_at.strftime("%Y-%m-%d %H:%M:%S"), f"{days}일 {hours}시간"

    @commands.command(name="clear")
    async def clear(self, ctx: commands.Context, amount: int | None = None) -> None:
        if not ctx.author.guild_permissions.administrator:
            await ctx.message.delete()
            await send_log(self.bot, ctx.author, "&clear", "권한 없는 사용자가 명령어 사용 시도")
            return

        if amount is None or amount < 1 or amount > CLEAR_LIMIT:
            await ctx.message.delete()
            await send_log(
                self.bot,
                ctx.author,
                "&clear",
                f"잘못된 인자 입력 — 사용법: &clear [횟수](최대 {CLEAR_LIMIT}개)",
            )
            return

        await ctx.message.delete()
        deleted = await ctx.channel.purge(limit=amount)
        await send_log(self.bot, ctx.author, "&clear", f"#{ctx.channel.name}에서 {len(deleted)}개 메시지 삭제")

    @app_commands.command(name="ping", description="봇의 응답 속도를 확인합니다.")
    @app_commands.guilds(GUILD)
    async def ping(self, interaction: discord.Interaction) -> None:
        latency = self.bot.latency * 1000
        await interaction.response.send_message(
            f"Pong! {latency:.2f}ms",
            ephemeral=False,
            delete_after=5,
        )
        await send_log(self.bot, interaction.user, "/ping", f"봇 응답 속도 확인 — {latency:.2f}ms")

    @app_commands.command(name="info", description="본인의 서버 정보를 확인합니다.")
    @app_commands.describe(보이기="다른 사용자에게도 보이게 할지 선택합니다.")
    @app_commands.guilds(GUILD)
    async def info(self, interaction: discord.Interaction, 보이기: bool = False) -> None:
        member = interaction.user
        ensure_user(member.id)

        joined_text, elapsed_text = self._build_join_info(member)
        info_data = {
            "joined_text": joined_text,
            "elapsed_text": elapsed_text,
            "is_advanced": self._has_info_advanced_role(member),
            "post_count": get_post_count(member.id),
            "end_count": get_end_count(member.id),
            "active_post_count": get_active_post_count(member.id),
            "total_promote_count": get_total_promote_count(member.id),
            "warning_count": get_warning_count(member.id),
            "balance": get_balance(member.id),
        }

        await interaction.response.send_message(embed=info_embed(member, info_data), ephemeral=not 보이기)
        await send_log(self.bot, member, "/info", "개인 정보 조회")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Etc(bot))
