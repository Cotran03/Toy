# ──────────────────────────────────────────────
#  cogs/verify.py  |  인증 관련 이벤트 + 버튼
# ──────────────────────────────────────────────
# Imports
import discord
from discord.ext import commands

# Import Config
from config import (
    ROLE_UNVERIFIED,
    ROLE_SCHOLAR,
    VERIFY_CHANNEL,
    VERIFY_MESSAGE_ID,
)

# Import Utils
from utils.send_log import send_log, send_system_log

# Import Views
from views.verify_embed import verify_embed


# ── Persistent View ───────────────────────────
class VerifyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # timeout=None → persistent

    @discord.ui.button(label="인증하기", style=discord.ButtonStyle.success, custom_id="verify_button")
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.user
        guild  = interaction.guild

        unverified_role = guild.get_role(ROLE_UNVERIFIED)
        scholar_role    = guild.get_role(ROLE_SCHOLAR)

        # 이미 인증된 유저 체크
        if scholar_role in member.roles:
            await interaction.response.send_message("이미 인증된 계정입니다.", ephemeral=True)
            await send_log(self.bot, member, "인증 시도", "이미 인증된 계정")
            return

        try:
            if unverified_role and unverified_role in member.roles:
                await member.remove_roles(unverified_role)
            if scholar_role:
                await member.add_roles(scholar_role)
                await send_log(self.bot, member, "인증 성공", "학자 역할 부여")
        except discord.Forbidden:
            await interaction.response.send_message("역할 부여에 실패했습니다. 관리자에게 문의해주세요.", ephemeral=True)
            await send_log(self.bot, member, "인증 실패", "역할 부여 권한 없음")
            return

        await interaction.response.defer()


class Verify(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        """Cog 로드 시 persistent View 등록 + 기존 메시지에 View 연결."""
        self.bot.add_view(VerifyView())
        self.bot.loop.create_task(self._attach_view())

    async def _attach_view(self):
        """VERIFY_MESSAGE_ID가 설정된 경우에만 메시지에 View 연결."""
        await self.bot.wait_until_ready()

        if not VERIFY_MESSAGE_ID:
            print("[verify] VERIFY_MESSAGE_ID 미설정 — &sendverify로 메시지를 먼저 전송하세요.")
            return

        channel = self.bot.get_channel(VERIFY_CHANNEL)
        if channel is None:
            print("[verify] 인증 채널을 찾을 수 없습니다.")
            return

        try:
            msg = await channel.fetch_message(VERIFY_MESSAGE_ID)
            await msg.edit(view=VerifyView())
            print(f"[verify] 인증 메시지 View 연결 완료 (ID: {VERIFY_MESSAGE_ID})")
        except discord.NotFound:
            print("[verify] 인증 메시지를 찾을 수 없습니다. VERIFY_MESSAGE_ID를 확인하세요.")
        except discord.Forbidden:
            print("[verify] 인증 메시지 수정 권한이 없습니다.")

    # ── Command: &sendverify ─────────────────────
    # 최초 1회만 사용. 전송 후 메시지 ID를 config/verify.py의 VERIFY_MESSAGE_ID에 입력 후 재시작
    @commands.command(name="sendverify")
    async def sendverify(self, ctx: commands.Context):
        if not ctx.author.guild_permissions.administrator:
            await ctx.message.delete()
            await send_log(self.bot, ctx.author, "&sendverify", "권한 없는 사용자가 명령어 사용 시도")
            return

        channel = self.bot.get_channel(VERIFY_CHANNEL)
        if channel is None:
            await ctx.send("인증 채널을 찾을 수 없습니다. VERIFY_CHANNEL를 확인하세요.", delete_after=5)
            await ctx.message.delete()
            return

        msg = await channel.send(embed=verify_embed(), view=VerifyView())

        await ctx.message.delete()
        print(f"[verify] 인증 메시지 ID: {msg.id} → config/verify.py의 VERIFY_MESSAGE_ID에 입력 후 재시작하세요.")
        await send_system_log(
            self.bot, "인증 메시지 전송",
            f"메시지 ID: `{msg.id}`\nconfig/verify.py의 `VERIFY_MESSAGE_ID`에 입력 후 봇을 재시작하세요."
        )

    # ── 이벤트: 멤버 입장 시 미인증 역할 자동 부여 ──
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        unverified_role = member.guild.get_role(ROLE_UNVERIFIED)
        if unverified_role:
            try:
                await member.add_roles(unverified_role)
                await send_system_log(self.bot, "멤버 입장", f"'{member}' ({member.id}) 미인증 역할 부여")
            except discord.Forbidden:
                print(f"[verify] '{member}' 미인증 역할 부여 실패 — 권한 부족")


async def setup(bot: commands.Bot):
    await bot.add_cog(Verify(bot))
