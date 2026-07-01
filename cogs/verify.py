import discord
from discord import app_commands
from discord.ext import commands

from config import GENERAL_ADMIN_ROLES, GUILD_ID, ROLE_SCHOLAR, ROLE_UNVERIFIED, VERIFY_CHANNEL, VERIFY_MESSAGE_ID
from db.database import get_verify_message_id, set_verify_message_id
from utils.app_permissions import any_role
from utils.activity_guard import deny_interaction_during_restore, is_restore_in_progress
from utils.interactions import send_ephemeral
from utils.send_log import send_log, send_system_log
from views.verify_embed import verify_embed


GUILD = discord.Object(id=GUILD_ID)


VERIFY_DM_MESSAGE = "인증이 완료되었습니다. 서버 규칙을 반드시 정독해 주시길 바랍니다."


class VerifyView(discord.ui.View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.bot = bot

    async def on_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
        item: discord.ui.Item,
    ) -> None:
        await send_system_log(
            self.bot,
            "인증 버튼 처리 실패",
            f"사용자: {interaction.user} ({interaction.user.id}) / {type(error).__name__}: {error}",
        )

    @discord.ui.button(label="인증하기", style=discord.ButtonStyle.success, custom_id="verify_button")
    async def verify_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        if await deny_interaction_during_restore(interaction, self.bot):
            return

        member = interaction.user
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("서버 정보를 가져오지 못했습니다.", ephemeral=True)
            return

        if guild.id != GUILD_ID:
            await interaction.response.send_message("이 인증 버튼은 이 서버에서 사용할 수 없습니다.", ephemeral=True)
            return

        unverified_role = guild.get_role(ROLE_UNVERIFIED)
        scholar_role = guild.get_role(ROLE_SCHOLAR)
        if unverified_role is None or scholar_role is None:
            missing = []
            if unverified_role is None:
                missing.append(f"미인증 역할 ({ROLE_UNVERIFIED})")
            if scholar_role is None:
                missing.append(f"학자 역할 ({ROLE_SCHOLAR})")
            details = f"인증 역할 설정 누락: {', '.join(missing)}"
            await interaction.response.send_message("인증 역할 설정 오류가 발생했습니다. 관리자에게 문의해주세요.", ephemeral=True)
            await send_system_log(self.bot, "인증 실패", details)
            return

        if scholar_role in member.roles:
            await interaction.response.send_message("이미 인증된 계정입니다.", ephemeral=True)
            await send_system_log(self.bot, "인증 시도", f"이미 인증된 계정 — {member} ({member.id})")
            return

        try:
            if unverified_role in member.roles:
                await member.remove_roles(unverified_role)
            await member.add_roles(scholar_role)
        except (discord.Forbidden, discord.HTTPException) as exc:
            await interaction.response.send_message(
                "역할 부여에 실패했습니다. 관리자에게 문의해주세요.",
                ephemeral=True,
            )
            await send_system_log(self.bot, "인증 실패", f"역할 부여 실패 — {member} ({member.id}) / {exc}")
            return

        try:
            await interaction.response.defer()
        except (discord.NotFound, discord.InteractionResponded):
            pass

        dm_sent = True
        try:
            await member.send(VERIFY_DM_MESSAGE)
        except (discord.Forbidden, discord.HTTPException):
            dm_sent = False

        log_details = f"'{member}' ({member.id}) 역할 부여 완료"
        if not dm_sent:
            log_details += "\nDM 전송 실패"
        await send_system_log(self.bot, "인증 성공", log_details)


class Verify(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.verify_message_id = get_verify_message_id(VERIFY_MESSAGE_ID)

    async def cog_load(self) -> None:
        self.bot.add_view(VerifyView(self.bot))

    @app_commands.command(name="verify", description="인증 채널에 인증 버튼 메시지를 전송합니다.")
    @app_commands.guilds(GUILD)
    @any_role(GENERAL_ADMIN_ROLES)
    async def sendverify(self, interaction: discord.Interaction) -> None:
        channel = self.bot.get_channel(VERIFY_CHANNEL)
        if channel is None:
            await send_ephemeral(interaction, "인증 채널을 찾을 수 없습니다.")
            await send_log(self.bot, interaction.user, "/verify", "인증 채널을 찾을 수 없음")
            return

        await interaction.response.defer(ephemeral=True)
        if self.verify_message_id:
            try:
                previous_message = await channel.fetch_message(self.verify_message_id)
                await previous_message.edit(view=None)
            except discord.NotFound:
                pass
            except (discord.Forbidden, discord.HTTPException) as exc:
                await send_system_log(
                    self.bot,
                    "인증 메시지 교체 실패",
                    f"기존 메시지 비활성화 실패 / ID: {self.verify_message_id} / {exc}",
                )

        message = await channel.send(embed=verify_embed(), view=VerifyView(self.bot))
        set_verify_message_id(message.id)
        self.verify_message_id = message.id

        await send_ephemeral(interaction, f"새 인증 메시지를 전송하고 자동 등록했습니다.\n메시지 ID: `{message.id}`")
        await send_log(
            self.bot,
            interaction.user,
            "/verify",
            f"인증 메시지 전송 / 메시지 ID: {message.id}",
        )
        await send_system_log(
            self.bot,
            "인증 메시지 전송",
            f"새 인증 메시지 자동 등록 / 메시지 ID: `{message.id}`",
        )

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        if is_restore_in_progress(self.bot):
            return

        if member.guild.id != GUILD_ID:
            return

        unverified_role = member.guild.get_role(ROLE_UNVERIFIED)
        if unverified_role is None:
            await send_system_log(
                self.bot,
                "멤버 입장 처리 실패",
                f"미인증 역할을 찾을 수 없음 / 역할 ID: {ROLE_UNVERIFIED} / 대상: {member} ({member.id})",
            )
            return

        try:
            await member.add_roles(unverified_role)
            await send_system_log(self.bot, "멤버 입장", f"'{member}' ({member.id}) 미인증 역할 부여")
        except (discord.Forbidden, discord.HTTPException) as exc:
            await send_system_log(self.bot, "멤버 입장 처리 실패", f"'{member}' ({member.id}) 미인증 역할 부여 실패 / {exc}")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Verify(bot))
