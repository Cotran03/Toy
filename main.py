import os
import sys

import discord
from discord import app_commands
from discord.ext import commands

from config import GUILD_ID, TOKEN
from db.backups import database_backup_loop
from db.database import init_db
from utils.app_command_visibility import apply_app_command_visibility
from utils.app_permissions import MissingAdminPermission
from utils.activity_guard import RESTORE_IN_PROGRESS_MESSAGE
from utils.interactions import send_ephemeral
from utils.send_log import send_log, send_system_log


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


class RestoreAwareCommandTree(app_commands.CommandTree):
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if getattr(self.client, "database_restore_in_progress", False):
            await interaction.response.send_message(
                RESTORE_IN_PROGRESS_MESSAGE,
                ephemeral=True,
            )
            command_name = f"/{interaction.command.qualified_name}" if interaction.command else "알 수 없는 명령어"
            await send_log(self.client, interaction.user, command_name, "DB 복구 중 명령어 사용 시도")
            return False

        return True

    async def on_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        command_name = f"/{interaction.command.qualified_name}" if interaction.command else "알 수 없는 명령어"
        original = error.original if isinstance(error, app_commands.CommandInvokeError) else error

        if isinstance(original, MissingAdminPermission):
            await send_ephemeral(interaction, "이 명령어를 사용할 권한이 없습니다.")
            await send_log(self.client, interaction.user, command_name, "권한 없는 사용자가 관리자 명령어 사용 시도")
            return

        await send_ephemeral(interaction, "명령어 처리 중 오류가 발생했습니다.")
        await send_log(
            self.client,
            interaction.user,
            command_name,
            f"명령어 오류: {type(original).__name__} / {original}",
        )
        print(f"[app_command_error] {command_name}: {original}")


class MyBot(commands.Bot):
    database_restore_in_progress: bool = False

    async def setup_hook(self) -> None:
        init_db()
        await load_extensions(self)
        is_paused = lambda: self.database_restore_in_progress
        self.backup_task = self.loop.create_task(
            database_backup_loop(
                is_paused,
                lambda exc: send_system_log(self, "DB 자동 백업 실패", str(exc)),
            )
        )

        self.tree.clear_commands(guild=None)
        await self.tree.sync()

        guild = discord.Object(id=GUILD_ID)
        synced_commands = await self.tree.sync(guild=guild)
        applied_visibility, visibility_failures = await apply_app_command_visibility(guild, synced_commands)
        print(f"[명령어 권한] {len(applied_visibility)}개 명령어 표시 권한 적용")
        if visibility_failures:
            await send_system_log(
                self,
                "명령어 표시 권한 적용 실패",
                "\n".join(visibility_failures),
            )


    async def on_error(self, event_method: str, *args, **kwargs) -> None:
        error = sys.exc_info()[1]
        await send_system_log(self, "이벤트 처리 실패", f"{event_method}: {error}")
        await super().on_error(event_method, *args, **kwargs)


bot = MyBot(
    command_prefix=commands.when_mentioned,
    intents=intents,
    help_command=None,
    tree_cls=RestoreAwareCommandTree,
)


@bot.event
async def on_ready() -> None:
    print(f"Logged in as {bot.user}")


bot.run(TOKEN)
