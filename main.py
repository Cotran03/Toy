import os

import discord
from discord.ext import commands

from config import GUILD_ID, TOKEN
from db.backups import database_backup_loop
from db.database import init_db
from utils.send_log import send_log


COMMAND_PREFIX = "&"
COG_DIR = "cogs"

intents = discord.Intents.all()


async def load_extensions(bot: commands.Bot) -> None:
    """COG_DIR 디렉토리에 있는 모든 .py 파일을 확장으로 불러옵니다."""
    for filename in os.listdir(COG_DIR):
        if not filename.endswith(".py"):
            continue

        extension = f"{COG_DIR}.{filename[:-3]}"
        print(f"{extension} 모듈을 불러옵니다.")
        await bot.load_extension(extension)


class MyBot(commands.Bot):
    async def setup_hook(self) -> None:
        init_db()
        self.backup_task = self.loop.create_task(database_backup_loop())
        await load_extensions(self)

        guild = discord.Object(id=GUILD_ID)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)


bot = MyBot(
    command_prefix=COMMAND_PREFIX,
    intents=intents,
    help_command=None,
)


@bot.event
async def on_ready() -> None:
    print(f"Logged in as {bot.user}")


@bot.command(name="sync")
async def sync(ctx: commands.Context) -> None:
    """관리자 전용: 슬래시 커맨드를 길드에 동기화합니다."""
    if not ctx.author.guild_permissions.administrator:
        await ctx.message.delete()
        await send_log(bot, ctx.author, "&sync", "권한 없는 사용자가 명령어 사용 시도")
        return

    guild = discord.Object(id=GUILD_ID)
    bot.tree.copy_global_to(guild=guild)
    synced = await bot.tree.sync(guild=guild)

    await ctx.message.delete()
    await ctx.send(f"슬래시 커맨드 {len(synced)}개 동기화 완료", delete_after=5)


@bot.command(name="reload")
async def reload(ctx: commands.Context) -> None:
    """관리자 전용: 모든 Cog를 다시 불러옵니다."""
    if not ctx.author.guild_permissions.administrator:
        await ctx.message.delete()
        await send_log(bot, ctx.author, "&reload", "권한 없는 사용자가 명령어 사용 시도")
        return

    results: list[str] = []
    for filename in os.listdir(COG_DIR):
        if not filename.endswith(".py"):
            continue

        extension = f"{COG_DIR}.{filename[:-3]}"
        try:
            await bot.reload_extension(extension)
            results.append(f"✅ {extension}")
        except Exception as exc:
            results.append(f"❌ {extension} — {exc}")

    await ctx.message.delete()
    await ctx.send("\n".join(results), delete_after=5)


bot.run(TOKEN)
