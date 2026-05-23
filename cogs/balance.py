import discord
from discord import app_commands
from discord.ext import commands

from config import BALANCER_ROLES, DAILY_REWARD_AMOUNT, GUILD_ID, STORE_ITEMS
from services.balance_service import (
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
    store_purchase_failed_embed,
    store_purchase_result_embed,
)


GUILD = discord.Object(id=GUILD_ID)
STORE_TIMEOUT_SECONDS = 180


class StoreView(discord.ui.View):
    def __init__(self, user_id: int, guild: discord.Guild):
        super().__init__(timeout=STORE_TIMEOUT_SECONDS)
        self.user_id = user_id
        self.guild = guild
        self.selected_role_id: int | None = None

        self.role_select = discord.ui.Select(
            placeholder="구매할 역할을 선택하세요.",
            min_values=1,
            max_values=1,
            options=self._build_role_options(),
        )
        self.role_select.callback = self.select_role
        self.add_item(self.role_select)

    def _build_role_options(self) -> list[discord.SelectOption]:
        options: list[discord.SelectOption] = []
        for role_id, item in STORE_ITEMS.items():
            role = self.guild.get_role(role_id)
            label = role.name if role else item["label"]
            options.append(
                discord.SelectOption(
                    label=label,
                    description=f"{item['label']} — {item['price']} INS",
                    value=str(role_id),
                    default=role_id == self.selected_role_id,
                )
            )
        return options

    def _refresh_role_options(self) -> None:
        self.role_select.options = self._build_role_options()

    async def _ensure_owner(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.user_id:
            return True

        embed = store_purchase_failed_embed(
            "구매 실패",
            "이 상점은 해당 명령어를 실행한 사용자만 사용할 수 있습니다.",
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        await send_log(
            interaction.client,
            interaction.user,
            "/store",
            "역할 구매 실패 / 사유: 다른 사용자의 상점 조작 시도",
        )
        return False

    async def _send_purchase_failure(
        self,
        interaction: discord.Interaction,
        title: str,
        description: str,
        *,
        reason: str,
        role_name: str | None = None,
        price: int | None = None,
        current_balance: int | None = None,
    ) -> None:
        embed = store_purchase_failed_embed(
            title,
            description,
            role_name=role_name,
            price=price,
            current_balance=current_balance,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

        details = f"역할 구매 실패 / 사유: {reason}"
        if role_name is not None:
            details += f" / 역할: {role_name}"
        if price is not None:
            details += f" / 가격: {price} INS"
        if current_balance is not None:
            details += f" / 잔액: {current_balance} INS"

        await send_log(interaction.client, interaction.user, "/store", details)

    async def select_role(self, interaction: discord.Interaction) -> None:
        if not await self._ensure_owner(interaction):
            return

        self.selected_role_id = int(self.role_select.values[0])
        self._refresh_role_options()
        await interaction.response.edit_message(
            embed=store_embed(
                self.guild,
                get_user_balance(self.user_id),
            ),
            view=self,
        )

    @discord.ui.button(label="구매", style=discord.ButtonStyle.primary)
    async def purchase_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        if not await self._ensure_owner(interaction):
            return

        if self.selected_role_id is None:
            await self._send_purchase_failure(
                interaction,
                "구매 실패",
                "먼저 드롭다운에서 구매할 역할을 선택해주세요.",
                reason="역할 미선택",
            )
            return

        guild = interaction.guild
        if guild is None:
            await self._send_purchase_failure(
                interaction,
                "구매 실패",
                "서버 정보를 가져오지 못했습니다.",
                reason="길드 정보 없음",
            )
            return

        member = interaction.user
        can_purchase, reason, role, item, balance = can_purchase_store_role(
            member,
            guild,
            self.selected_role_id,
        )

        if reason == "not_found":
            await self._send_purchase_failure(
                interaction,
                "구매 실패",
                "선택한 역할 정보를 찾을 수 없습니다.",
                reason="역할 정보 없음",
            )
            return

        if reason == "already_owned":
            await self._send_purchase_failure(
                interaction,
                "구매 실패",
                "이미 해당 역할을 보유하고 있습니다.",
                reason="이미 보유",
                role_name=role.name,
            )
            return

        if reason == "insufficient_balance":
            price = item["price"]
            await self._send_purchase_failure(
                interaction,
                "잔액 부족",
                f"{role.name} 역할 구매에 필요한 INS가 부족합니다.",
                reason="잔액 부족",
                role_name=role.name,
                price=price,
                current_balance=balance,
            )
            return

        if reason == "missing_promoter":
            await self._send_purchase_failure(
                interaction,
                "구매 실패",
                "홍보대사는 홍보자 역할을 보유한 상태에서만 구매할 수 있습니다.",
                reason="홍보자 역할 없음",
                role_name=role.name,
                price=item["price"],
                current_balance=balance,
            )
            return

        if not can_purchase:
            await self._send_purchase_failure(
                interaction,
                "구매 실패",
                "구매를 처리할 수 없습니다.",
                reason=reason,
                role_name=role.name if role else None,
            )
            return

        try:
            await member.add_roles(role)
        except discord.Forbidden:
            await self._send_purchase_failure(
                interaction,
                "구매 실패",
                "역할 부여 권한이 없습니다. 관리자에게 문의해주세요.",
                reason="역할 부여 권한 없음",
                role_name=role.name,
                price=item["price"],
                current_balance=balance,
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
            f"역할 구매 성공 / 역할: {role.name} / 사용: {price} INS / 잔액: {new_balance} INS",
        )


class Balance(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _ensure_balancer(self, ctx: commands.Context, command_name: str) -> bool:
        if has_any_role(ctx.author, BALANCER_ROLES):
            return True

        await ctx.message.delete()
        await send_log(self.bot, ctx.author, command_name, "권한 없는 사용자가 명령어 사용 시도")
        return False

    @app_commands.command(name="reward", description="하루에 한 번 INS를 받습니다.")
    @app_commands.guilds(GUILD)
    async def reward(self, interaction: discord.Interaction) -> None:
        claimed, _ = claim_daily_reward(interaction.user.id)
        if not claimed:
            await interaction.response.send_message(
                "오늘은 이미 보상을 받았습니다. 내일 다시 시도해주세요.",
                ephemeral=False,
            )
            return

        await interaction.response.send_message(
            f"오늘의 보상으로 {DAILY_REWARD_AMOUNT} INS를 받았습니다.",
            ephemeral=False,
        )
        await send_log(self.bot, interaction.user, "/reward", "일일 보상 수령")

    @app_commands.command(name="store", description="INS로 역할을 구매합니다.")
    @app_commands.guilds(GUILD)
    async def store(self, interaction: discord.Interaction) -> None:
        current_balance = get_user_balance(interaction.user.id)
        view = StoreView(interaction.user.id, interaction.guild)
        await interaction.response.send_message(
            embed=store_embed(interaction.guild, current_balance),
            view=view,
            ephemeral=True,
        )

    @commands.command(name="addINS")
    async def add_ins(
        self,
        ctx: commands.Context,
        member: discord.Member,
        amount: int,
        *,
        reason: str = "관리자에 의해 추가됨",
    ) -> None:
        if not await self._ensure_balancer(ctx, "&addINS"):
            return

        new_balance = add_user_balance(member.id, amount)
        await ctx.send(f"{member.mention}님에게 {amount} INS를 추가했습니다. 현재 잔액: {new_balance} INS.")
        await send_log(self.bot, ctx.author, "&addINS", f"대상: {member} / {amount} INS / 사유: {reason}")

    @commands.command(name="delINS")
    async def del_ins(
        self,
        ctx: commands.Context,
        member: discord.Member,
        amount: int,
        *,
        reason: str = "관리자에 의해 차감됨",
    ) -> None:
        if not await self._ensure_balancer(ctx, "&delINS"):
            return

        new_balance = deduct_user_balance(member.id, amount)
        await ctx.send(f"{member.mention}님의 INS를 {amount}만큼 차감했습니다. 현재 잔액: {new_balance} INS.")
        await send_log(self.bot, ctx.author, "&delINS", f"대상: {member} / {amount} INS / 사유: {reason}")

    @commands.command(name="resetINS")
    async def reset_ins(
        self,
        ctx: commands.Context,
        member: discord.Member,
        *,
        reason: str,
    ) -> None:
        if not await self._ensure_balancer(ctx, "&resetINS"):
            return

        new_balance = reset_user_balance(member.id)
        await ctx.send(f"{member.mention}님의 INS를 0으로 설정했습니다.")
        await send_log(self.bot, ctx.author, "&resetINS", f"대상: {member} / 잔액: {new_balance} INS / 사유: {reason}")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Balance(bot))
