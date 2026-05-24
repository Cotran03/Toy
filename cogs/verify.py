import discord
from discord.ext import commands

from config import ROLE_SCHOLAR, ROLE_UNVERIFIED, VERIFY_CHANNEL, VERIFY_MESSAGE_ID
from utils.send_log import send_log, send_system_log
from views.verify_embed import verify_embed


VERIFY_DM_MESSAGE = "인증이 완료되었습니다. 서버 규칙을 반드시 정독해 주시길 바랍니다."


class VerifyView(discord.ui.View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="인증하기", style=discord.ButtonStyle.success, custom_id="verify_button")
    async def verify_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        member = interaction.user
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("서버 정보를 가져오지 못했습니다.", ephemeral=True)
            return

        unverified_role = guild.get_role(ROLE_UNVERIFIED)
        scholar_role = guild.get_role(ROLE_SCHOLAR)

        if scholar_role and scholar_role in member.roles:
            await interaction.response.send_message("이미 인증된 계정입니다.", ephemeral=True)
            await send_system_log(self.bot, "인증 시도", "이미 인증된 계정")
            return

        try:
            if unverified_role and unverified_role in member.roles:
                await member.remove_roles(unverified_role)
            if scholar_role:
                await member.add_roles(scholar_role)
        except discord.Forbidden:
            await interaction.response.send_message(
                "역할 부여에 실패했습니다. 관리자에게 문의해주세요.",
                ephemeral=True,
            )
            await send_system_log(self.bot, "인증 실패", "역할 부여 실패 — 권한 부족")
            return

        await interaction.response.defer()

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

    async def cog_load(self) -> None:
        self.bot.add_view(VerifyView(self.bot))
        self.bot.loop.create_task(self._attach_view())

    async def _attach_view(self) -> None:
        await self.bot.wait_until_ready()

        if not VERIFY_MESSAGE_ID:
            print("[verify] VERIFY_MESSAGE_ID 미설정 — &sendverify로 메시지를 먼저 전송하세요.")
            return

        channel = self.bot.get_channel(VERIFY_CHANNEL)
        if channel is None:
            print("[verify] 인증 채널을 찾을 수 없습니다.")
            return

        try:
            message = await channel.fetch_message(VERIFY_MESSAGE_ID)
            await message.edit(view=VerifyView(self.bot))
            print(f"[verify] 인증 메시지 View 연결 완료 (ID: {VERIFY_MESSAGE_ID})")
        except discord.NotFound:
            print("[verify] 인증 메시지를 찾을 수 없습니다. VERIFY_MESSAGE_ID를 확인하세요.")
        except discord.Forbidden:
            print("[verify] 인증 메시지 수정 권한이 없습니다.")

    @commands.command(name="sendverify")
    async def sendverify(self, ctx: commands.Context) -> None:
        if not ctx.author.guild_permissions.administrator:
            await ctx.message.delete()
            await send_log(self.bot, ctx.author, "&sendverify", "권한 없는 사용자가 명령어 사용 시도")
            return

        channel = self.bot.get_channel(VERIFY_CHANNEL)
        if channel is None:
            await ctx.send("인증 채널을 찾을 수 없습니다. VERIFY_CHANNEL을 확인하세요.", delete_after=5)
            await ctx.message.delete()
            return

        message = await channel.send(embed=verify_embed(), view=VerifyView(self.bot))
        await ctx.message.delete()

        print(f"[verify] 인증 메시지 ID: {message.id} — config/verify.py의 VERIFY_MESSAGE_ID에 입력한 뒤 재시작하세요.")
        await send_system_log(
            self.bot,
            "인증 메시지 전송",
            f"메시지 ID: `{message.id}`\nconfig/verify.py의 `VERIFY_MESSAGE_ID`에 입력한 뒤 봇을 재시작하세요.",
        )

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        unverified_role = member.guild.get_role(ROLE_UNVERIFIED)
        if unverified_role is None:
            return

        try:
            await member.add_roles(unverified_role)
            await send_system_log(self.bot, "멤버 입장", f"'{member}' ({member.id}) 미인증 역할 부여")
        except discord.Forbidden:
            print(f"[verify] '{member}' 미인증 역할 부여 실패 — 권한 부족")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Verify(bot))
