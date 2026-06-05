import os

import discord
from discord import app_commands
from discord.ext import commands

from config import GUILD_ID, TOKEN, ADMIN_PREFIX, USER_CREATOR
from config.bot2 import SECONDARY_GUILD_ID
from db.backups import database_backup_loop, list_backups, restore_database
from db.database import init_db
from utils.send_log import send_command_result, send_log


COG_DIR = "cogs"
RESTORE_IN_PROGRESS_MESSAGE = "DB 복구 중입니다. 잠시 후 다시 시도해 주세요."

intents = discord.Intents.all()


async def load_extensions(bot: commands.Bot) -> None:
    """COG_DIR 디렉토리에 있는 모든 .py 파일을 확장으로 불러옵니다."""
    for filename in os.listdir(COG_DIR):
        if not filename.endswith(".py"):
            continue

        extension = f"{COG_DIR}.{filename[:-3]}"
        print(f"{extension} 모듈을 불러옵니다.")
        await bot.load_extension(extension)


class RestoreAwareCommandTree(app_commands.CommandTree):
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if getattr(self.client, "database_restore_in_progress", False):
            await interaction.response.send_message(
                RESTORE_IN_PROGRESS_MESSAGE,
                ephemeral=True,
            )
            return False

        return True


class MyBot(commands.Bot):
    database_restore_in_progress: bool = False

    async def setup_hook(self) -> None:
        init_db()
        self.backup_task = self.loop.create_task(database_backup_loop())
        await load_extensions(self)

        self.tree.clear_commands(guild=None)
        await self.tree.sync()

        guild = discord.Object(id=GUILD_ID)
        await self.tree.sync(guild=guild)

        if SECONDARY_GUILD_ID > 0:
            secondary_guild = discord.Object(id=SECONDARY_GUILD_ID)
            await self.tree.sync(guild=secondary_guild)


bot = MyBot(
    command_prefix=ADMIN_PREFIX,
    intents=intents,
    help_command=None,
    tree_cls=RestoreAwareCommandTree,
)


@bot.check
async def prefix_command_gate(ctx: commands.Context) -> bool:
    if ctx.guild is None or ctx.guild.id != GUILD_ID:
        setattr(ctx, "silent_guild_block", True)
        return False

    if bot.database_restore_in_progress:
        await ctx.message.delete()
        command_name = f"{ADMIN_PREFIX}{ctx.command.qualified_name}" if ctx.command else "unknown"
        await send_command_result(bot, f"{command_name} 결과", RESTORE_IN_PROGRESS_MESSAGE)
        await send_log(bot, ctx.author, command_name, "DB 복구 중 명령어 사용 시도")
        return False

    return True


@bot.event
async def on_ready() -> None:
    print(f"Logged in as {bot.user}")


@bot.command(name="sync")
async def sync(ctx: commands.Context) -> None:
    """관리자 전용: 슬래시 커맨드를 길드에 동기화합니다."""
    await ctx.message.delete()

    if ctx.author.id != USER_CREATOR:
        await send_log(bot, ctx.author, "&sync", "권한 없는 사용자가 명령어 사용 시도")
        return

    guild = discord.Object(id=GUILD_ID)
    bot.tree.clear_commands(guild=None)
    global_synced = await bot.tree.sync()
    synced = await bot.tree.sync(guild=guild)
    secondary_synced = []
    if SECONDARY_GUILD_ID > 0:
        secondary_guild = discord.Object(id=SECONDARY_GUILD_ID)
        secondary_synced = await bot.tree.sync(guild=secondary_guild)

    result = (
        f"첫 번째 서버 슬래시 커맨드: {len(synced)}개\n"
        f"두 번째 서버 슬래시 커맨드: {len(secondary_synced)}개\n"
        f"전역 슬래시 커맨드 정리: {len(global_synced)}개"
    )
    await send_command_result(bot, "&sync 결과", result)
    await send_log(bot, ctx.author, "&sync", "슬래시 커맨드 동기화 실행")


@bot.command(name="reload")
async def reload(ctx: commands.Context) -> None:
    """관리자 전용: 모든 Cog를 다시 불러옵니다."""
    await ctx.message.delete()

    if ctx.author.id != USER_CREATOR:
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

    await send_command_result(bot, "&reload 결과", "\n".join(results))
    await send_log(bot, ctx.author, "&reload", "Cog reload 실행")


@bot.command(name="backups")
async def backups(ctx: commands.Context) -> None:
    """Admin only: list available database backups."""
    await ctx.message.delete()

    if ctx.author.id != USER_CREATOR:
        await send_log(bot, ctx.author, "&backups", "권한 없는 사용자가 명령어 사용 시도")
        return

    backup_paths = await bot.loop.run_in_executor(None, list_backups)
    if not backup_paths:
        await send_command_result(bot, "&backups 결과", "DB 백업본 없음")
        await send_log(bot, ctx.author, "&backups", "DB 백업 목록 조회")
        return

    lines = ["사용 가능한 DB 백업본:"]
    for index, path in enumerate(backup_paths[:10], start=1):
        lines.append(f"{index}. `{path.name}`")

    if len(backup_paths) > 10:
        lines.append(f"...외 {len(backup_paths) - 10}개")

    await send_command_result(bot, "&backups 결과", "\n".join(lines))
    await send_log(bot, ctx.author, "&backups", f"DB 백업 목록 조회 / {len(backup_paths)}개")


@bot.command(name="restoredb")
async def restoredb(ctx: commands.Context, backup_name: str | None = None) -> None:
    """Admin only: restore the database from a backup."""
    await ctx.message.delete()

    if ctx.author.id != USER_CREATOR:
        await send_log(bot, ctx.author, "&restoredb", "권한 없는 사용자가 명령어 사용 시도")
        return

    if backup_name is None:
        await send_command_result(bot, "&restoredb 결과", "사용법: &restoredb latest 또는 &restoredb 백업파일명.db")
        await send_log(bot, ctx.author, "&restoredb", "사용법 오류")
        return

    bot.database_restore_in_progress = True
    try:
        try:
            restored_from, safety_backup = await bot.loop.run_in_executor(
                None,
                restore_database,
                backup_name,
            )
        except Exception as exc:
            await send_command_result(bot, "&restoredb 결과", f"DB 복구 실패: {exc}")
            await send_log(bot, ctx.author, "&restoredb", "DB 복구 실패")
            return
    finally:
        bot.database_restore_in_progress = False

    safety_text = safety_backup.name if safety_backup else "없음"
    result = f"복구본: {restored_from.name}\n복구 전 안전 백업: {safety_text}"
    await send_command_result(bot, "&restoredb 결과", result)
    await send_log(bot, ctx.author, "&restoredb", f"DB 복구 실행 / {restored_from.name}")


@bot.event
async def on_command_error(ctx: commands.Context, error: Exception) -> None:
    if isinstance(error, commands.CheckFailure):
        return

    try:
        await ctx.message.delete()
    except (discord.Forbidden, discord.NotFound):
        pass

    command_name = f"{ADMIN_PREFIX}{ctx.command.qualified_name}" if ctx.command else "unknown"
    await send_command_result(bot, f"{command_name} 결과", f"명령어 오류: {error}")
    await send_log(bot, ctx.author, command_name, f"명령어 오류: {type(error).__name__}")


bot.run(TOKEN)
