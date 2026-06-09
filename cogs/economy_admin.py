import discord
from discord import app_commands
from discord.ext import commands

from config import GUILD_ID, USER_CREATOR
from db.database import (
    ECONOMY_SETTING_DEFAULTS,
    get_all_economy_settings,
    get_store_items,
    reset_economy_setting,
    reset_store_price,
    set_economy_setting,
    set_store_price,
)
from utils.send_log import send_command_result, send_log


SETTING_LABELS = {
    "daily_reward": "일일 보상",
    "end_reward": "포스트 종료 보상",
    "warn_penalty": "경고 재화 차감",
    "promote_cost": "홍보 비용",
}
SETTING_ALIASES = {
    "daily": "daily_reward",
    "daily_reward": "daily_reward",
    "일일보상": "daily_reward",
    "end": "end_reward",
    "end_reward": "end_reward",
    "종료보상": "end_reward",
    "warn": "warn_penalty",
    "warn_penalty": "warn_penalty",
    "경고차감": "warn_penalty",
    "promote": "promote_cost",
    "promote_cost": "promote_cost",
    "홍보비용": "promote_cost",
}
MAX_ECONOMY_VALUE = 1_000_000_000
GUILD = discord.Object(id=GUILD_ID)


class EconomyAdmin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _ensure_creator(self, ctx: commands.Context, command_name: str) -> bool:
        await ctx.message.delete()
        if ctx.author.id == USER_CREATOR:
            return True

        await send_log(self.bot, ctx.author, command_name, "권한 없는 사용자가 경제 설정 변경 시도")
        return False

    async def _send_usage_error(self, ctx: commands.Context, command_name: str, details: str) -> None:
        await send_command_result(self.bot, f"{command_name} 결과", details)
        await send_log(self.bot, ctx.author, command_name, "사용법 오류")

    def _resolve_setting_key(self, value: str) -> str | None:
        return SETTING_ALIASES.get(value.lower())

    def _valid_value(self, value: int) -> bool:
        return 0 <= value <= MAX_ECONOMY_VALUE

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

    @commands.group(name="economy", invoke_without_command=True, hidden=True)
    async def economy_admin(self, ctx: commands.Context) -> None:
        await ctx.message.delete()
        await send_log(self.bot, ctx.author, "&economy", "/economy 사용 안내")

    @economy_admin.command(name="set")
    async def economy_set(self, ctx: commands.Context, setting: str | None = None, value: int | None = None) -> None:
        if not await self._ensure_creator(ctx, "&economy set"):
            return

        key = self._resolve_setting_key(setting) if setting else None
        if key is None or value is None or not self._valid_value(value):
            await self._send_usage_error(
                ctx,
                "&economy set",
                "사용법: `&economy set [항목] [0~1,000,000,000]`\n"
                f"항목: {', '.join(SETTING_LABELS)}",
            )
            return

        old_value = get_all_economy_settings()[key]
        set_economy_setting(key, value)
        await send_command_result(
            self.bot,
            "&economy set 결과",
            f"{SETTING_LABELS[key]}: {old_value:,} → {value:,} INS",
        )
        await send_log(
            self.bot,
            ctx.author,
            "&economy set",
            f"{key}: {old_value} -> {value}",
        )

    @economy_admin.command(name="reset")
    async def economy_reset(self, ctx: commands.Context, setting: str | None = None) -> None:
        if not await self._ensure_creator(ctx, "&economy reset"):
            return

        key = self._resolve_setting_key(setting) if setting else None
        if key is None:
            await self._send_usage_error(
                ctx,
                "&economy reset",
                "사용법: `&economy reset [항목]`\n"
                f"항목: {', '.join(SETTING_LABELS)}",
            )
            return

        old_value = get_all_economy_settings()[key]
        default_value = reset_economy_setting(key)
        await send_command_result(
            self.bot,
            "&economy reset 결과",
            f"{SETTING_LABELS[key]}: {old_value:,} → 기본값 {default_value:,} INS",
        )
        await send_log(
            self.bot,
            ctx.author,
            "&economy reset",
            f"{key}: {old_value} -> default {default_value}",
        )

    @economy_admin.command(name="store")
    async def economy_store(
        self,
        ctx: commands.Context,
        role: discord.Role | None = None,
        price: int | None = None,
    ) -> None:
        if not await self._ensure_creator(ctx, "&economy store"):
            return

        store_items = get_store_items()
        if role is None or role.id not in store_items or price is None or not self._valid_value(price):
            await self._send_usage_error(
                ctx,
                "&economy store",
                "사용법: `&economy store @상점역할 [0~1,000,000,000]`",
            )
            return

        old_price = store_items[role.id]["price"]
        set_store_price(role.id, price)
        await send_command_result(
            self.bot,
            "&economy store 결과",
            f"{role.name}: {old_price:,} → {price:,} INS",
        )
        await send_log(
            self.bot,
            ctx.author,
            "&economy store",
            f"{role.name} ({role.id}): {old_price} -> {price}",
        )

    @economy_admin.command(name="resetstore")
    async def economy_reset_store(
        self,
        ctx: commands.Context,
        role: discord.Role | None = None,
    ) -> None:
        if not await self._ensure_creator(ctx, "&economy resetstore"):
            return

        store_items = get_store_items()
        if role is None or role.id not in store_items:
            await self._send_usage_error(
                ctx,
                "&economy resetstore",
                "사용법: `&economy resetstore @상점역할`",
            )
            return

        old_price = store_items[role.id]["price"]
        default_price = reset_store_price(role.id)
        await send_command_result(
            self.bot,
            "&economy resetstore 결과",
            f"{role.name}: {old_price:,} → 기본값 {default_price:,} INS",
        )
        await send_log(
            self.bot,
            ctx.author,
            "&economy resetstore",
            f"{role.name} ({role.id}): {old_price} -> default {default_price}",
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(EconomyAdmin(bot))
