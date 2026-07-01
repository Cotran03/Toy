import asyncio
from collections import defaultdict

import discord
from discord import app_commands
from discord.ext import commands

from config import BALANCER_ROLES, ECONOMY_CHANNEL, GUILD_ID
from services.balance_service import (
    add_user_balance,
    can_purchase_store_role,
    claim_daily_reward,
    complete_store_purchase,
    deduct_user_balance,
    get_current_store_items,
    get_daily_reward_amount,
    get_user_balance,
    refund_store_purchase,
    reset_user_balance,
)
from utils.app_permissions import any_role
from utils.activity_guard import deny_interaction_during_restore
from utils.interactions import send_ephemeral
from utils.send_log import send_log, send_system_log
from views.balance_embed import (
    economy_admin_notice_embed,
    reward_embed,
    store_embed,
    store_purchase_failed_embed,
    store_purchase_result_embed,
)


GUILD = discord.Object(id=GUILD_ID)
STORE_TIMEOUT_SECONDS = 180


class StoreView(discord.ui.View):
    def __init__(
        self,
        bot: commands.Bot,
        user_id: int,
        guild: discord.Guild,
        purchase_lock: asyncio.Lock,
    ):
        super().__init__(timeout=STORE_TIMEOUT_SECONDS)
        self.bot = bot
        self.user_id = user_id
        self.guild = guild
        self.purchase_lock = purchase_lock
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
        for role_id, item in get_current_store_items().items():
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

    async def on_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
        item: discord.ui.Item,
    ) -> None:
        await send_log(self.bot, interaction.user, "/store", f"상점 UI 오류: {type(error).__name__} / {error}")

    def _refresh_role_options(self) -> None:
        self.role_select.options = self._build_role_options()

    def _disable_all_items(self) -> None:
        for item in self.children:
            item.disabled = True

    async def _send_ephemeral(
        self,
        interaction: discord.Interaction,
        embed: discord.Embed,
    ) -> None:
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _resolve_member(self, interaction: discord.Interaction) -> discord.Member | None:
        if isinstance(interaction.user, discord.Member):
            return interaction.user

        if interaction.guild is None:
            return None

        member = interaction.guild.get_member(interaction.user.id)
        if member is not None:
            return member

        try:
            return await interaction.guild.fetch_member(interaction.user.id)
        except discord.NotFound:
            return None

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
        await self._send_ephemeral(interaction, embed)

        details = f"역할 구매 실패 / 사유: {reason}"
        if role_name is not None:
            details += f" / 역할: {role_name}"
        if price is not None:
            details += f" / 가격: {price} INS"
        if current_balance is not None:
            details += f" / 잔액: {current_balance} INS"

        await send_log(self.bot, interaction.user, "/store", details)

    async def select_role(self, interaction: discord.Interaction) -> None:
        if await deny_interaction_during_restore(interaction, self.bot):
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

    async def _complete_purchase(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        guild: discord.Guild,
        role_id: int,
    ) -> None:
        async with self.purchase_lock:
            can_purchase, reason, role, item, balance = can_purchase_store_role(member, guild, role_id)
            if not can_purchase or role is None or item is None:
                await self._send_purchase_failure(
                    interaction,
                    "구매 실패",
                    "구매 대기 중 역할 보유 상태, 상점 설정 또는 잔액이 변경되었습니다.",
                    reason=f"구매 직전 재검사 실패: {reason}",
                    role_name=role.name if role else None,
                    price=item["price"] if item else None,
                    current_balance=balance,
                )
                return

            price = item["price"]
            new_balance = complete_store_purchase(member.id, price)
            if new_balance is None:
                await self._send_purchase_failure(
                    interaction,
                    "잔액 부족",
                    "구매 처리 중 잔액이 변경되어 필요한 INS가 부족합니다.",
                    reason="선차감 실패",
                    role_name=role.name,
                    price=price,
                    current_balance=get_user_balance(member.id),
                )
                return

            try:
                await member.add_roles(role)
            except (discord.Forbidden, discord.HTTPException) as exc:
                try:
                    refunded_balance = refund_store_purchase(member.id, price)
                    failure_reason = f"역할 부여 실패 후 환불: {type(exc).__name__}"
                    description = "역할 부여에 실패하여 사용한 INS를 환불했습니다."
                except Exception as refund_exc:
                    refunded_balance = get_user_balance(member.id)
                    failure_reason = f"역할 부여 및 환불 실패: {type(exc).__name__} / {refund_exc}"
                    description = "역할 부여와 INS 환불에 실패했습니다. 관리자에게 문의해주세요."
                await self._send_purchase_failure(
                    interaction,
                    "구매 실패",
                    description,
                    reason=failure_reason,
                    role_name=role.name,
                    price=price,
                    current_balance=refunded_balance,
                )
                return

            self._disable_all_items()
            await interaction.edit_original_response(
                embed=store_purchase_result_embed(role.name, price, new_balance),
                view=self,
            )
            await send_log(
                self.bot,
                member,
                "/store",
                f"역할 구매 성공 / 역할: {role.name} / 사용: {price} INS / 잔액: {new_balance} INS",
            )

    @discord.ui.button(label="구매", style=discord.ButtonStyle.primary)
    async def purchase_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        if await deny_interaction_during_restore(interaction, self.bot):
            return

        await interaction.response.defer()

        if self.selected_role_id is None:
            await self._send_purchase_failure(
                interaction,
                "구매 실패",
                "먼저 드롭다운에서 구매할 역할을 선택해주세요.",
                reason="역할 미선택",
            )
            return
        selected_role_id = self.selected_role_id

        guild = interaction.guild
        if guild is None:
            await self._send_purchase_failure(
                interaction,
                "구매 실패",
                "서버 정보를 가져오지 못했습니다.",
                reason="길드 정보 없음",
            )
            return

        member = await self._resolve_member(interaction)
        if member is None:
            await self._send_purchase_failure(
                interaction,
                "구매 실패",
                "사용자 정보를 가져오지 못했습니다. 잠시 후 다시 시도해주세요.",
                reason="멤버 정보 없음",
            )
            return

        can_purchase, reason, role, item, balance = can_purchase_store_role(
            member,
            guild,
            selected_role_id,
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

        await self._complete_purchase(interaction, member, guild, selected_role_id)


class Balance(commands.Cog):
    balance_admin = app_commands.Group(
        name="balance",
        description="사용자 INS를 관리합니다.",
        guild_ids=[GUILD_ID],
    )

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.store_purchase_locks: defaultdict[int, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def _economy_channel(self) -> discord.abc.Messageable | None:
        channel = self.bot.get_channel(ECONOMY_CHANNEL)
        if channel is not None:
            return channel

        try:
            return await self.bot.fetch_channel(ECONOMY_CHANNEL)
        except (discord.Forbidden, discord.NotFound, discord.HTTPException) as exc:
            print(f"[economy_notice] 경제 채널 조회 실패 ({ECONOMY_CHANNEL}): {exc}")
            await send_system_log(self.bot, "경제 공지 실패", f"경제 채널 조회 실패 ({ECONOMY_CHANNEL}) / {exc}")
            return None

    async def _send_economy_notice(
        self,
        moderator: discord.User | discord.Member,
        member: discord.Member,
        action: str,
        amount_text: str,
        reason: str,
    ) -> None:
        channel = await self._economy_channel()
        if channel is None or not hasattr(channel, "send"):
            return

        try:
            await channel.send(
                embed=economy_admin_notice_embed(
                    moderator,
                    member,
                    action,
                    amount_text,
                    reason,
                )
            )
        except (discord.Forbidden, discord.HTTPException) as exc:
            print(f"[economy_notice] 경제 공지 전송 실패 ({ECONOMY_CHANNEL}): {exc}")
            await send_system_log(self.bot, "경제 공지 실패", f"경제 공지 전송 실패 ({ECONOMY_CHANNEL}) / {exc}")

    @app_commands.command(name="reward", description="하루에 한 번 INS를 받습니다.")
    @app_commands.guilds(GUILD)
    async def reward(self, interaction: discord.Interaction) -> None:
        reward_amount = get_daily_reward_amount()
        claimed, balance, reward_streak, last_reward_date = claim_daily_reward(interaction.user.id)
        if not claimed:
            await interaction.response.send_message(
                embed=reward_embed(
                    claimed=False,
                    amount=reward_amount,
                    balance=balance,
                    reward_streak=reward_streak,
                    last_reward_date=last_reward_date,
                ),
                ephemeral=False,
            )
            await send_log(
                self.bot,
                interaction.user,
                "/reward",
                f"이미 수령한 일일 보상 요청 / 잔액: {balance} INS / 연속 출석: {reward_streak}일 / 마지막 수령일: {last_reward_date}",
            )
            return

        await interaction.response.send_message(
            embed=reward_embed(
                claimed=True,
                amount=reward_amount,
                balance=balance,
                reward_streak=reward_streak,
                last_reward_date=last_reward_date,
            ),
            ephemeral=False,
        )
        await send_log(
            self.bot,
            interaction.user,
            "/reward",
            f"일일 보상 수령 / 지급: {reward_amount} INS / 잔액: {balance} INS / 연속 출석: {reward_streak}일",
        )

    @app_commands.command(name="store", description="INS로 역할을 구매합니다.")
    @app_commands.guilds(GUILD)
    async def store(self, interaction: discord.Interaction) -> None:
        current_balance = get_user_balance(interaction.user.id)
        view = StoreView(
            self.bot,
            interaction.user.id,
            interaction.guild,
            self.store_purchase_locks[interaction.user.id],
        )
        await interaction.response.send_message(
            embed=store_embed(interaction.guild, current_balance),
            view=view,
            ephemeral=True,
        )

    @balance_admin.command(name="add", description="사용자에게 INS를 추가합니다.")
    @app_commands.describe(member="INS를 추가할 사용자", amount="추가할 INS", reason="추가 사유")
    @any_role(BALANCER_ROLES)
    async def add_ins(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        amount: app_commands.Range[int, 1, 1_000_000_000],
        reason: str = "관리자에 의해 추가됨",
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        balance = add_user_balance(member.id, amount)
        await self._send_economy_notice(interaction.user, member, "추가", f"+{amount:,} INS", reason)
        await send_ephemeral(interaction, f"{member.mention}에게 {amount:,} INS를 추가했습니다.\n현재 잔액: {balance:,} INS")
        await send_log(
            self.bot,
            interaction.user,
            "/balance add",
            f"대상: {member} / {amount} INS / 사유: {reason}",
        )

    @balance_admin.command(name="remove", description="사용자의 INS를 차감합니다.")
    @app_commands.describe(member="INS를 차감할 사용자", amount="차감할 INS", reason="차감 사유")
    @any_role(BALANCER_ROLES)
    async def del_ins(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        amount: app_commands.Range[int, 1, 1_000_000_000],
        reason: str = "관리자에 의해 차감됨",
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        balance = deduct_user_balance(member.id, amount)
        await self._send_economy_notice(interaction.user, member, "차감", f"-{amount:,} INS", reason)
        await send_ephemeral(interaction, f"{member.mention}에게서 {amount:,} INS를 차감했습니다.\n현재 잔액: {balance:,} INS")
        await send_log(
            self.bot,
            interaction.user,
            "/balance remove",
            f"대상: {member} / {amount} INS / 사유: {reason}",
        )

    @balance_admin.command(name="reset", description="사용자의 INS 잔액을 초기화합니다.")
    @app_commands.describe(member="INS를 초기화할 사용자", reason="초기화 사유")
    @any_role(BALANCER_ROLES)
    async def reset_ins(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        reset_user_balance(member.id)
        await self._send_economy_notice(interaction.user, member, "초기화", "전체 INS 초기화", reason)
        await send_ephemeral(interaction, f"{member.mention}의 INS 잔액을 초기화했습니다.")
        await send_log(
            self.bot,
            interaction.user,
            "/balance reset",
            f"대상: {member} / 초기화 / 사유: {reason}",
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Balance(bot))
