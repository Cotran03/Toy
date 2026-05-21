import os

import discord
from discord.ext import commands

from config import GUILD_ID, TOKEN
from db.backups import database_backup_loop, list_backups, restore_database
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


@bot.command(name="backups")
async def backups(ctx: commands.Context) -> None:
    """Admin only: list available database backups."""
    if not ctx.author.guild_permissions.administrator:
        await ctx.message.delete()
        await send_log(bot, ctx.author, "&backups", "권한 없는 사용자가 명령어 사용 시도")
        return

    backup_paths = await bot.loop.run_in_executor(None, list_backups)
    if not backup_paths:
        await ctx.message.delete()
        await ctx.send("DB 백업본이 없습니다.", delete_after=10)
        return

    lines = ["사용 가능한 DB 백업본:"]
    for index, path in enumerate(backup_paths[:10], start=1):
        lines.append(f"{index}. `{path.name}`")

    if len(backup_paths) > 10:
        lines.append(f"...외 {len(backup_paths) - 10}개")

    await ctx.message.delete()
    await ctx.send("\n".join(lines), delete_after=30)


@bot.command(name="restoredb")
async def restoredb(ctx: commands.Context, backup_name: str | None = None) -> None:
    """Admin only: restore the database from a backup."""
    if not ctx.author.guild_permissions.administrator:
        await ctx.message.delete()
        await send_log(bot, ctx.author, "&restoredb", "권한 없는 사용자가 명령어 사용 시도")
        return

    if backup_name is None:
        await ctx.message.delete()
        await ctx.send("사용법: `&restoredb latest` 또는 `&restoredb 백업파일명.db`", delete_after=15)
        return

    try:
        restored_from, safety_backup = await bot.loop.run_in_executor(
            None,
            restore_database,
            backup_name,
        )
    except Exception as exc:
        await ctx.message.delete()
        await ctx.send(f"DB 복구 실패: `{exc}`", delete_after=15)
        await send_log(bot, ctx.author, "&restoredb", f"DB 복구 실패: {exc}")
        return

    safety_text = safety_backup.name if safety_backup else "없음"
    await ctx.message.delete()
    await ctx.send(
        f"DB 복구 완료: `{restored_from.name}`\n복구 전 안전 백업: `{safety_text}`\n봇 재시작을 권장합니다.",
        delete_after=30,
    )
    await send_log(
        bot,
        ctx.author,
        "&restoredb",
        f"복구본: {restored_from.name} / 복구 전 안전 백업: {safety_text}",
    )


bot.run(TOKEN)
