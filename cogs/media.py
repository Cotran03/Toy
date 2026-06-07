import asyncio
from dataclasses import dataclass

import discord
from discord.ext import commands

from config import BOT_COMMAND_CHANNEL, MEDIA_CHANNEL


MEDIA_NOTICE = "미디어방에서 채팅은 삼가해주시길 바랍니다."
BOT_COMMAND_NOTICE = """
# 관리자 명령어
&sync : 슬래시 명령어를 현재 길드에 동기화합니다.

&reload : 모든 Cog를 다시 불러와 봇 기능을 갱신합니다.

&clear [개수:필수] : 현재 채널의 메시지를 지정한 개수만큼 삭제합니다.

&info @유저 : 대상 유저의 상세 서버 정보를 조회합니다.

&sendverify : 인증 채널에 인증 버튼 메시지를 전송합니다.

&addINS @유저 [금액] [사유:선택] : 대상 유저에게 INS를 추가합니다.

&delINS @유저 [금액] [사유:선택] : 대상 유저의 INS를 차감합니다.

&resetINS @유저 [사유:필수] : 대상 유저의 INS 잔액을 0으로 초기화합니다.

&warn @유저 [개수] [사유:필수] : 대상 유저에게 경고를 부여하고 누적 경고에 따른 제재를 적용합니다.

&warnoff @유저/유저ID : 대상 유저의 경고를 1개 차감하고 필요 시 제재를 해제합니다.

&backups : 현재 보관 중인 DB 백업본 목록을 최신순으로 표시합니다.

&restoredb latest : 가장 최신 DB 백업본으로 현재 DB를 복구합니다.

&restoredb [백업파일명.db] : 지정한 DB 백업 파일로 현재 DB를 복구합니다.

&economy: 현재 경제 설정과 상점 가격을 조회합니다.

&economy set [항목] [값]: 보상·차감·비용 설정값을 변경합니다.
> 일일 보상: daily_reward, daily, 일일보상
> 포스트 종료 보상:    end_reward, end, 종료보상
> 경고 재화 차감:    warn_penalty, warn, 경고차감
> 홍보 비용:    promote_cost, promote, 홍보비용

&economy reset [항목]: 경제 설정을 config/economy.py 기본값으로 복원합니다.

&economy store @역할 [가격]: 상점 역할의 가격을 변경합니다.

&economy resetstore @역할: 상점 역할 가격을 config/store.py 기본값으로 복원합니다.
> 상점에 등록된 역할 이름
""".strip()
NOTICE_HISTORY_LIMIT = 100
MESSAGE_CONTENT_LIMIT = 2000


@dataclass(frozen=True)
class ChannelAutomationRule:
    channel_id: int
    notice: str
    refresh_on_all_messages: bool = True
    create_threads_for_attachments: bool = False
    include_bot_messages: bool = True
    thread_fallback_name: str = "첨부파일"


CHANNEL_AUTOMATION_RULES = {
    MEDIA_CHANNEL: ChannelAutomationRule(
        channel_id=MEDIA_CHANNEL,
        notice=MEDIA_NOTICE,
        refresh_on_all_messages=False,
        create_threads_for_attachments=True,
        include_bot_messages=False,
        thread_fallback_name="미디어",
    ),
    BOT_COMMAND_CHANNEL: ChannelAutomationRule(
        channel_id=BOT_COMMAND_CHANNEL,
        notice=BOT_COMMAND_NOTICE,
    ),
}


class ChannelAutomation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.initial_notices_sent = False
        self.notice_messages: dict[int, list[discord.Message]] = {}
        self.notice_locks: dict[int, asyncio.Lock] = {
            channel_id: asyncio.Lock() for channel_id in CHANNEL_AUTOMATION_RULES
        }

    async def _get_text_channel(self, channel_id: int) -> discord.TextChannel | None:
        channel = self.bot.get_channel(channel_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except (discord.Forbidden, discord.NotFound, discord.HTTPException) as exc:
                print(f"[channel_automation] 채널 조회 실패 ({channel_id}): {exc}")
                return None

        if not isinstance(channel, discord.TextChannel):
            print(f"[channel_automation] 텍스트 채널이 아닙니다 ({channel_id})")
            return None

        return channel

    def _notice_chunks(self, notice: str) -> list[str]:
        chunks: list[str] = []
        remaining = notice

        while len(remaining) > MESSAGE_CONTENT_LIMIT:
            split_at = remaining.rfind("\n", 0, MESSAGE_CONTENT_LIMIT + 1)
            if split_at <= 0:
                split_at = MESSAGE_CONTENT_LIMIT

            chunks.append(remaining[:split_at])
            remaining = remaining[split_at:]
            if remaining.startswith("\n"):
                remaining = remaining[1:]

        if remaining:
            chunks.append(remaining)

        return chunks

    def _thread_name(self, message: discord.Message, rule: ChannelAutomationRule) -> str:
        content = message.content.strip().splitlines()[0] if message.content.strip() else ""
        name = content or f"{message.author.display_name}님의 {rule.thread_fallback_name}"
        return name[:100]

    async def _create_thread(self, message: discord.Message, rule: ChannelAutomationRule) -> None:
        try:
            await message.create_thread(name=self._thread_name(message, rule))
        except (discord.Forbidden, discord.HTTPException) as exc:
            print(f"[channel_automation] 스레드 생성 실패 ({message.id}): {exc}")

    async def _find_previous_notice(
        self,
        channel: discord.TextChannel,
        notice_chunks: list[str],
    ) -> list[discord.Message]:
        if self.bot.user is None:
            return []

        try:
            history = [message async for message in channel.history(limit=NOTICE_HISTORY_LIMIT)]
        except (discord.Forbidden, discord.HTTPException) as exc:
            print(f"[channel_automation] 기존 안내 메시지 조회 실패 ({channel.id}): {exc}")
            return []

        notice_count = len(notice_chunks)
        for start in range(len(history) - notice_count + 1):
            messages = history[start : start + notice_count]
            if any(message.author.id != self.bot.user.id for message in messages):
                continue

            if [message.content for message in reversed(messages)] == notice_chunks:
                return messages

        return []

    async def _refresh_notice(
        self,
        channel: discord.TextChannel,
        rule: ChannelAutomationRule,
    ) -> None:
        if not rule.notice:
            return

        notice_chunks = self._notice_chunks(rule.notice)
        async with self.notice_locks[channel.id]:
            previous_notices = self.notice_messages.get(channel.id)
            if previous_notices is None:
                previous_notices = await self._find_previous_notice(channel, notice_chunks)

            for previous_notice in previous_notices:
                try:
                    await previous_notice.delete()
                except discord.NotFound:
                    pass
                except (discord.Forbidden, discord.HTTPException) as exc:
                    print(f"[channel_automation] 기존 안내 메시지 삭제 실패 ({previous_notice.id}): {exc}")

            sent_notices: list[discord.Message] = []
            try:
                for notice_chunk in notice_chunks:
                    sent_notices.append(await channel.send(notice_chunk))

                self.notice_messages[channel.id] = sent_notices
            except (discord.Forbidden, discord.HTTPException) as exc:
                if sent_notices:
                    self.notice_messages[channel.id] = sent_notices
                else:
                    self.notice_messages.pop(channel.id, None)
                print(f"[channel_automation] 안내 메시지 전송 실패 ({channel.id}): {exc}")

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        if self.initial_notices_sent:
            return

        self.initial_notices_sent = True
        for rule in CHANNEL_AUTOMATION_RULES.values():
            if not rule.notice:
                continue

            channel = await self._get_text_channel(rule.channel_id)
            if channel is not None:
                await self._refresh_notice(channel, rule)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        rule = CHANNEL_AUTOMATION_RULES.get(message.channel.id)
        if rule is None or not rule.notice:
            return

        if not isinstance(message.channel, discord.TextChannel):
            return

        notice_chunks = self._notice_chunks(rule.notice)
        if (
            self.bot.user is not None
            and message.author.id == self.bot.user.id
            and message.content in notice_chunks
        ):
            return

        if message.author.bot and not rule.include_bot_messages:
            return

        has_attachments = bool(message.attachments)
        if rule.create_threads_for_attachments and has_attachments:
            await self._create_thread(message, rule)

        if rule.refresh_on_all_messages or has_attachments:
            await self._refresh_notice(message.channel, rule)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ChannelAutomation(bot))
