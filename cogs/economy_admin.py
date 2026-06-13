import discord
from discord import app_commands
from discord.ext import commands

from config import GUILD_ID, SYSTEM_ADMIN_ROLES
from db.database import (
    ECONOMY_SETTING_DEFAULTS,
    get_all_economy_settings,
    get_store_items,
    reset_economy_setting,
    reset_store_price,
    set_economy_setting,
    set_store_price,
)
from utils.app_permissions import any_role
from utils.interactions import send_ephemeral
from utils.send_log import send_log


SETTING_LABELS = {
    "daily_reward": "일일 보상",
    "end_reward": "포스트 종료 보상",
    "warn_penalty": "경고 재화 차감",
    "promote_cost": "홍보 비용",
}
MAX_ECONOMY_VALUE = 1_000_000_000
GUILD = discord.Object(id=GUILD_ID)
SETTING_CHOICES = [
    app_commands.Choice(name=label, value=key)
    for key, label in SETTING_LABELS.items()
]


class EconomyAdmin(commands.Cog):
    economy_admin = app_commands.Group(
        name="seteconomy",
        description="경제 설정과 상점 가격을 관리합니다.",
        guild_ids=[GUILD_ID],
    )

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _build_summary(self, guild: discord.Guild) -> str:
        settings = get_all_economy_settings()
        store_items = get_store_items()

        lines = ["현재 경제 설정"]
        for key, value in settings.items():
            default = ECONOMY_SETTING_DEFAULTS[key]
            lines.append(f"- `{key}` ({SETTING_LABELS[key]}): {value:,} INS (기본값 {default:,})")

        lines.append("\n상점 역할 가격")
        for role_id, item in store_items.items():
            role = guild.get_role(role_id)
            role_name = (role.name if role else item["label"])[:40]
            lines.append(f"- {role_name}: {item['price']:,} INS")

        return "\n".join(lines)

    @app_commands.command(name="economy", description="현재 경제 설정과 상점 가격을 확인합니다.")
    @app_commands.guilds(GUILD)
    async def economy(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("서버 정보를 가져올 수 없습니다.", ephemeral=True)
            return

        embed = discord.Embed(
            title="현재 경제 설정",
            description=self._build_summary(interaction.guild),
            color=0x5865F2,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        await send_log(self.bot, interaction.user, "/economy", "경제 설정 조회")

    @economy_admin.command(name="set", description="보상, 차감, 비용 설정값을 변경합니다.")
    @app_commands.describe(setting="변경할 경제 설정", value="새 설정값")
    @app_commands.choices(setting=SETTING_CHOICES)
    @any_role(SYSTEM_ADMIN_ROLES)
    async def economy_set(
        self,
        interaction: discord.Interaction,
        setting: app_commands.Choice[str],
        value: app_commands.Range[int, 0, MAX_ECONOMY_VALUE],
    ) -> None:
        key = setting.value
        old_value = get_all_economy_settings()[key]
        set_economy_setting(key, value)
        await send_ephemeral(interaction, f"{SETTING_LABELS[key]}: {old_value:,} → {value:,} INS")
        await send_log(
            self.bot,
            interaction.user,
            "/seteconomy set",
            f"{key}: {old_value} -> {value}",
        )

    @economy_admin.command(name="reset", description="경제 설정값을 기본값으로 복원합니다.")
    @app_commands.describe(setting="기본값으로 복원할 경제 설정")
    @app_commands.choices(setting=SETTING_CHOICES)
    @any_role(SYSTEM_ADMIN_ROLES)
    async def economy_reset(
        self,
        interaction: discord.Interaction,
        setting: app_commands.Choice[str],
    ) -> None:
        key = setting.value
        old_value = get_all_economy_settings()[key]
        default_value = reset_economy_setting(key)
        await send_ephemeral(interaction, f"{SETTING_LABELS[key]}: {old_value:,} → 기본값 {default_value:,} INS")
        await send_log(
            self.bot,
            interaction.user,
            "/seteconomy reset",
            f"{key}: {old_value} -> default {default_value}",
        )

    @economy_admin.command(name="store", description="상점 역할 가격을 변경합니다.")
    @app_commands.describe(role="가격을 변경할 상점 역할", price="새 가격")
    @any_role(SYSTEM_ADMIN_ROLES)
    async def economy_store(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
        price: app_commands.Range[int, 0, MAX_ECONOMY_VALUE],
    ) -> None:
        store_items = get_store_items()
        if role.id not in store_items:
            await send_ephemeral(interaction, "상점에 등록된 역할만 가격을 변경할 수 있습니다.")
            await send_log(self.bot, interaction.user, "/seteconomy store", f"등록되지 않은 역할: {role.id}")
            return

        old_price = store_items[role.id]["price"]
        set_store_price(role.id, price)
        await send_ephemeral(interaction, f"{role.name}: {old_price:,} → {price:,} INS")
        await send_log(
            self.bot,
            interaction.user,
            "/seteconomy store",
            f"{role.name} ({role.id}): {old_price} -> {price}",
        )

    @economy_admin.command(name="reset-store", description="상점 역할 가격을 기본값으로 복원합니다.")
    @app_commands.describe(role="가격을 기본값으로 복원할 상점 역할")
    @any_role(SYSTEM_ADMIN_ROLES)
    async def economy_reset_store(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
    ) -> None:
        store_items = get_store_items()
        if role.id not in store_items:
            await send_ephemeral(interaction, "상점에 등록된 역할만 가격을 복원할 수 있습니다.")
            await send_log(self.bot, interaction.user, "/seteconomy reset-store", f"등록되지 않은 역할: {role.id}")
            return

        old_price = store_items[role.id]["price"]
        default_price = reset_store_price(role.id)
        await send_ephemeral(interaction, f"{role.name}: {old_price:,} → 기본값 {default_price:,} INS")
        await send_log(
            self.bot,
            interaction.user,
            "/seteconomy reset-store",
            f"{role.name} ({role.id}): {old_price} -> default {default_price}",
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(EconomyAdmin(bot))
