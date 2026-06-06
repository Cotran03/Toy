import asyncio

import discord
from discord.ext import commands

from config import MEDIA_CHANNEL


MEDIA_NOTICE = "미디어방에서 채팅은 삼가해주시길 바랍니다."
NOTICE_HISTORY_LIMIT = 100


class Media(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.notice_message: discord.Message | None = None
        self.notice_lock = asyncio.Lock()

    def _thread_name(self, message: discord.Message) -> str:
        content = message.content.strip().splitlines()[0] if message.content.strip() else ""
        name = content or f"{message.author.display_name}님의 미디어"
        return name[:100]

    async def _create_thread(self, message: discord.Message) -> None:
        try:
            await message.create_thread(name=self._thread_name(message))
        except (discord.Forbidden, discord.HTTPException) as exc:
            print(f"[media] 스레드 생성 실패 ({message.id}): {exc}")

    async def _find_previous_notice(self, channel: discord.TextChannel) -> discord.Message | None:
        if self.bot.user is None:
            return None

        try:
            async for history_message in channel.history(limit=NOTICE_HISTORY_LIMIT):
                if history_message.author.id == self.bot.user.id and history_message.content == MEDIA_NOTICE:
                    return history_message
        except (discord.Forbidden, discord.HTTPException) as exc:
            print(f"[media] 기존 안내 메시지 조회 실패 ({channel.id}): {exc}")

        return None

    async def _refresh_notice(self, channel: discord.TextChannel) -> None:
        async with self.notice_lock:
            previous_notice = self.notice_message
            if previous_notice is None or previous_notice.channel.id != channel.id:
                previous_notice = await self._find_previous_notice(channel)

            if previous_notice is not None:
                try:
                    await previous_notice.delete()
                except discord.NotFound:
                    pass
                except (discord.Forbidden, discord.HTTPException) as exc:
                    print(f"[media] 기존 안내 메시지 삭제 실패 ({previous_notice.id}): {exc}")

            try:
                self.notice_message = await channel.send(MEDIA_NOTICE)
            except (discord.Forbidden, discord.HTTPException) as exc:
                self.notice_message = None
                print(f"[media] 안내 메시지 전송 실패 ({channel.id}): {exc}")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.channel.id != MEDIA_CHANNEL or not message.attachments or message.author.bot:
            return

        if not isinstance(message.channel, discord.TextChannel):
            return

        await self._create_thread(message)
        await self._refresh_notice(message.channel)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Media(bot))
