# ──────────────────────────────────────────────
#  cogs/etc.py  |  기타 관리자 커맨드
# ──────────────────────────────────────────────
import discord
from discord.ext import commands

from utils.send_log import send_log


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


async def setup(bot: commands.Bot):
    await bot.add_cog(Etc(bot))