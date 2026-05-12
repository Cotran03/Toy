# ──────────────────────────────────────────────
#  cogs/etc.py  |  기타 커맨드
# ──────────────────────────────────────────────
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime

from utils.send_log import send_log
from views.etc_embed import info_embed

from config import GUILD_ID, ROLE_INFO_ADVANCED, ROLE_SHOP_ACCESS
from db.database import (
    ensure_user,
    get_post_count,
    get_end_count,
    get_total_promote_count,
    get_warning_count,
    get_balance,
)


class Etc(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # Command: &clear [횟수]
    @commands.command(name="clear")
    async def clear(self, ctx: commands.Context, amount: int = None):
        if not ctx.author.guild_permissions.administrator:
            await ctx.message.delete()
            await send_log(self.bot, ctx.author, "&clear", "권한 없는 사용자가 명령어 사용 시도")
            return

        if amount is None or amount < 1 or amount > 100:
            await ctx.message.delete()
            await send_log(self.bot, ctx.author, "&clear", "인자 누락 또는 잘못된 값 — 사용법: &clear [횟수](최대 100개)")
            return

        await ctx.message.delete()
        deleted = await ctx.channel.purge(limit=amount)
        await send_log(self.bot, ctx.author, "&clear", f"#{ctx.channel.name} 에서 {len(deleted)}개 메시지 삭제")

    # Command: /ping
    @app_commands.command(name="ping", description="봇의 응답 속도를 확인합니다.")
    @app_commands.guilds(GUILD_ID)
    async def ping(self, interaction: discord.Interaction):
        latency = self.bot.latency * 1000
        await interaction.response.send_message(f"Pong! {latency:.2f}ms", ephemeral=False, delete_after=5)
        await send_log(self.bot, interaction.user, "/ping", f"봇 응답 속도 확인 — {latency:.2f}ms")


    # Command: /info
    @app_commands.command(name="info", description="본인의 서버 내 정보를 확인합니다.")
    @app_commands.guilds(GUILD_ID)
    async def info(self, interaction: discord.Interaction):
        member = interaction.user
        ensure_user(member.id)

        is_advanced = any(role.id == ROLE_INFO_ADVANCED for role in member.roles)
        has_shop_access = any(role.id == ROLE_SHOP_ACCESS for role in member.roles)

        joined_at = getattr(member, "joined_at", None)
        if joined_at is None:
            joined_text = "알 수 없음"
            elapsed_text = "알 수 없음"
        else:
            joined_text = joined_at.strftime("%Y-%m-%d %H:%M:%S")
            now = datetime.now(tz=joined_at.tzinfo) if joined_at.tzinfo else datetime.utcnow()
            elapsed = now - joined_at
            days = elapsed.days
            hours = elapsed.seconds // 3600
            elapsed_text = f"{days}일 {hours}시간"

        info_data = {
            "joined_text": joined_text,
            "elapsed_text": elapsed_text,
            "is_advanced": is_advanced,
            "has_shop_access": has_shop_access,
            "post_count": get_post_count(member.id),
            "end_count": get_end_count(member.id),
            "total_promote_count": get_total_promote_count(member.id),
            "warning_count": get_warning_count(member.id),
            "balance": get_balance(member.id),
        }

        await interaction.response.send_message(embed=info_embed(member, info_data), ephemeral=False)
        await send_log(self.bot, member, "/info", "개인 정보 조회")


async def setup(bot: commands.Bot):
    await bot.add_cog(Etc(bot))