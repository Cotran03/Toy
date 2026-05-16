# ──────────────────────────────────────────────
#  views/verify_embed.py  |  cogs/verify.py 전용 Embed
# ──────────────────────────────────────────────
# Imports
from datetime import datetime, timezone

import discord


def verify_embed() -> discord.Embed:
    """인증 채널에 상시 표시되는 인증 안내 Embed."""
    embed = discord.Embed(
        title="✅ 사용자 인증",
        description="아래 버튼을 눌러 인증을 완료하세요.\n인증 후 서버의 모든 채널을 이용할 수 있습니다.",
        color=0x57F287,
        timestamp=datetime.now(timezone.utc),
    )
    return embed
