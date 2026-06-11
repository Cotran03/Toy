import discord
from discord import app_commands
from discord.ext import commands

from config.bot2 import SECONDARY_GUILD_ID, WARN_DEBUG_CHANNEL
from db.secondary_backups import list_secondary_backups, restore_secondary_database
from utils.app_permissions import creator_only
from utils.interactions import send_ephemeral
from utils.operation_locks import get_operation_lock
from utils.send_log import send_log


class SecondarySystemAdmin(commands.Cog):
    database_admin = app_commands.Group(
        name="database",
        description="두 번째 서버 데이터베이스 백업과 복구를 관리합니다.",
        guild_ids=[SECONDARY_GUILD_ID],
        default_permissions=discord.Permissions.none(),
    )

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _require_debug_channel(self, interaction: discord.Interaction) -> bool:
        if interaction.channel_id == WARN_DEBUG_CHANNEL:
            return True

        await send_ephemeral(
            interaction,
            f"두 번째 서버 DB 조회와 변경은 <#{WARN_DEBUG_CHANNEL}>에서만 진행할 수 있습니다.",
        )
        return False

    @database_admin.command(name="backups", description="두 번째 서버 DB 백업본을 확인합니다.")
    @creator_only()
    async def backups(self, interaction: discord.Interaction) -> None:
        if not await self._require_debug_channel(interaction):
            return

        await interaction.response.defer(ephemeral=True)
        backup_paths = await self.bot.loop.run_in_executor(None, list_secondary_backups)
        if not backup_paths:
            await send_ephemeral(interaction, "두 번째 서버 DB 백업본이 없습니다.")
            await send_log(self.bot, interaction.user, "/database backups", "두 번째 서버 DB 백업 목록 조회 / 0개")
            return

        lines = ["사용 가능한 두 번째 서버 DB 백업본:"]
        lines.extend(f"{index}. `{path.name}`" for index, path in enumerate(backup_paths[:10], start=1))
        if len(backup_paths) > 10:
            lines.append(f"...외 {len(backup_paths) - 10}개")

        await send_ephemeral(interaction, "\n".join(lines))
        await send_log(
            self.bot,
            interaction.user,
            "/database backups",
            f"두 번째 서버 DB 백업 목록 조회 / {len(backup_paths)}개",
        )

    @database_admin.command(name="restore", description="두 번째 서버 DB를 지정한 백업본으로 복구합니다.")
    @app_commands.describe(backup_name="latest 또는 복구할 백업 파일명")
    @creator_only()
    async def restore(self, interaction: discord.Interaction, backup_name: str) -> None:
        if not await self._require_debug_channel(interaction):
            return

        await interaction.response.defer(ephemeral=True)
        restore_lock = get_operation_lock(self.bot, "database_restore", 0)
        if restore_lock.locked():
            await send_ephemeral(interaction, "이미 다른 DB 복구가 진행 중입니다.")
            await send_log(self.bot, interaction.user, "/database restore", "중복 두 번째 서버 DB 복구 시도 차단")
            return

        async with restore_lock:
            self.bot.database_restore_in_progress = True
            try:
                try:
                    restored_from, safety_backup = await self.bot.loop.run_in_executor(
                        None,
                        restore_secondary_database,
                        backup_name,
                    )
                except Exception as exc:
                    await send_ephemeral(interaction, f"두 번째 서버 DB 복구 실패: {exc}")
                    await send_log(self.bot, interaction.user, "/database restore", f"두 번째 서버 DB 복구 실패 / {exc}")
                    return
            finally:
                self.bot.database_restore_in_progress = False

        safety_text = safety_backup.name if safety_backup else "없음"
        await send_ephemeral(
            interaction,
            f"복구본: `{restored_from.name}`\n복구 전 안전 백업: `{safety_text}`",
        )
        await send_log(
            self.bot,
            interaction.user,
            "/database restore",
            f"두 번째 서버 DB 복구 실행 / {restored_from.name}",
        )


async def setup(bot: commands.Bot) -> None:
    if SECONDARY_GUILD_ID > 0:
        await bot.add_cog(SecondarySystemAdmin(bot))
