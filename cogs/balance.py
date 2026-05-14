# ──────────────────────────────────────────────
#  cogs/balance.py  |  잔고 관련 커맨드
# ──────────────────────────────────────────────

import discord
from discord import app_commands
from discord.ext import commands

from config import GUILD_ID, BALANCER_ROLES, STORE_ITEMS
from services.balance_service import (
    DAILY_REWARD_AMOUNT,
    add_user_balance,
    can_purchase_store_role,
    claim_daily_reward,
    complete_store_purchase,
    deduct_user_balance,
    get_user_balance,
    reset_user_balance,
)
from utils.check_permission import has_any_role
from utils.send_log import send_log
from views.balance_embed import (
    store_embed,
    store_purchase_result_embed,
    store_purchase_failed_embed,
)

GUILD = discord.Object(id=GUILD_ID)


class StoreView(discord.ui.View):
    def __init__(self, user_id: int, guild: discord.Guild):
        super().__init__(timeout=180)
        self.user_id = user_id
        self.guild = guild
        self.selected_role_id: int | None = None

        options = []
        for role_id, item in STORE_ITEMS.items():
            role = guild.get_role(role_id)
            label = role.name if role else item["label"]
            options.append(
                discord.SelectOption(
                    label=label,
                    description=f"{item['label']} — {item['price']} INS",
                    value=str(role_id),
                )
            )

        self.role_select = discord.ui.Select(
            placeholder="구매할 역할을 선택하세요.",
            min_values=1,
            max_values=1,
            options=options,
        )
        self.role_select.callback = self.select_role
        self.add_item(self.role_select)

    async def select_role(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "이 상점은 해당 명령어를 실행한 사용자만 사용할 수 있습니다.",
                ephemeral=True,
            )
            return

        self.selected_role_id = int(self.role_select.values[0])
        await interaction.response.edit_message(
            embed=store_embed(self.guild, get_user_balance(self.user_id), self.selected_role_id),
            view=self,
        )

    @discord.ui.button(label="구매", style=discord.ButtonStyle.primary)
    async def purchase_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "이 상점은 해당 명령어을 실행한 사용자만 사용할 수 있습니다.",
                ephemeral=True,
            )
            return

        if self.selected_role_id is None:
            await interaction.response.send_message(
                "먼저 드롭다운에서 구매할 역할을 선택해주세요.",
                ephemeral=True,
            )
            return

        member = interaction.user
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("서버 정보를 가져오지 못했습니다.", ephemeral=True)
            return

        can_purchase, reason, role, item, balance = can_purchase_store_role(
            member,
            guild,
            self.selected_role_id,
        )

        if reason == "not_found":
            await interaction.response.send_message(
                "선택한 역할 정보를 찾을 수 없습니다.",
                ephemeral=True,
            )
            return

        if reason == "already_owned":
            await interaction.response.send_message(
                "이미 해당 역할을 보유하고 있습니다.",
                ephemeral=True,
            )
            return

        if reason == "insufficient_balance":
            price = item["price"]
            await interaction.response.send_message(
                embed=store_purchase_failed_embed(role.name, price, balance),
                ephemeral=True,
            )
            return

        if not can_purchase:
            await interaction.response.send_message("구매를 처리할 수 없습니다.", ephemeral=True)
            return

        try:
            await member.add_roles(role)
        except discord.Forbidden:
            await interaction.response.send_message(
                "역할 부여 권한이 없습니다. 관리자에게 문의해주세요.",
                ephemeral=True,
            )
            return

        price = item["price"]
        new_balance = complete_store_purchase(member.id, price)
        self.disable_all_items()
        await interaction.response.edit_message(
            embed=store_purchase_result_embed(role.name, price, new_balance),
            view=self,
        )

        await send_log(
            interaction.client,
            member,
            "/store",
            f"{role.name} 역할 구매 / {price} INS 사용 / 남은 잔액 {new_balance} INS",
        )


class Balance(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="reward", description="하루에 한 번 INS를 받습니다.")
    @app_commands.guilds(GUILD)
    async def reward(self, interaction: discord.Interaction):
        claimed, _ = claim_daily_reward(interaction.user.id)
        if not claimed:
            await interaction.response.send_message(
                "오늘은 이미 보상을 받았습니다. 내일 다시 시도해주세요.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            f"🎉 오늘의 보상으로 {DAILY_REWARD_AMOUNT} INS를 받았습니다!",
            ephemeral=True,
        )
        await send_log(self.bot, interaction.user, "/reward", "일일 보상 수령")

    @app_commands.command(name="store", description="INS로 역할을 구매합니다.")
    @app_commands.guilds(GUILD)
    async def store(self, interaction: discord.Interaction):
        current_balance = get_user_balance(interaction.user.id)
        view = StoreView(interaction.user.id, interaction.guild)
        await interaction.response.send_message(
            embed=store_embed(interaction.guild, current_balance),
            view=view,
            ephemeral=True,
        )

    @commands.command(name="addINS")
    async def add_ins(self, ctx: commands.Context, member: discord.Member, amount: int, *, reason: str = "관리자에 의해 추가됨"):
        if not has_any_role(ctx.author, BALANCER_ROLES):
            await ctx.message.delete()
            await send_log(self.bot, ctx.author, "&addINS", "권한 없는 사용자가 명령어 사용 시도")
            return

        new_balance = add_user_balance(member.id, amount)
        await ctx.send(f"{member.mention}님에게 {amount} INS를 추가했습니다. 현재 잔액: {new_balance} INS.")
        await send_log(self.bot, ctx.author, "&addINS", f"대상: {member} / {amount} INS / 사유: {reason}")

    @commands.command(name="delINS")
    async def del_ins(self, ctx: commands.Context, member: discord.Member, amount: int, *, reason: str = "관리자에 의해 차감됨"):
        if not has_any_role(ctx.author, BALANCER_ROLES):
            await ctx.message.delete()
            await send_log(self.bot, ctx.author, "&delINS", "권한 없는 사용자가 명령어 사용 시도")
            return

        new_balance = deduct_user_balance(member.id, amount)
        await ctx.send(f"{member.mention}님의 INS를 {amount}만큼 차감했습니다. 현재 잔액: {new_balance} INS.")
        await send_log(self.bot, ctx.author, "&delINS", f"대상: {member} / {amount} INS / 사유: {reason}")

    @commands.command(name="resetINS")
    async def reset_ins(self, ctx: commands.Context, member: discord.Member, amount: int, *, reason: str):
        if not has_any_role(ctx.author, BALANCER_ROLES):
            await ctx.message.delete()
            await send_log(self.bot, ctx.author, "&resetINS", "권한 없는 사용자가 명령어 사용 시도")
            return

        new_balance = reset_user_balance(member.id)
        await ctx.send(f"{member.mention}님의 INS를 0으로 설정했습니다.")
        await send_log(self.bot, ctx.author, "&resetINS", f"대상: {member} / 잔액: {new_balance} INS / 사유: {reason}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Balance(bot))
