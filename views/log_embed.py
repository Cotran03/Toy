# Imports
from datetime import datetime, timezone
import discord


EMBED_FIELD_LIMIT = 1024
LOG_CATEGORY_LABELS = {
    "command": "일반 명령어",
    "admin": "관리자",
    "economy": "경제",
    "discussion": "토론",
    "warning": "경고",
    "verify": "인증",
    "database": "데이터베이스",
    "system": "시스템",
}
LOG_STATUS_COLORS = {
    "success": 0x57F287,
    "warning": 0xFEE75C,
    "failure": 0xED4245,
}
FAILURE_KEYWORDS = ("실패", "오류", "예외")
WARNING_KEYWORDS = (
    "권한 없는",
    "사용 시도",
    "찾을 수 없음",
    "차단",
    "초과",
    "누락",
    "부족",
    "중복",
    "처리 중",
)


def _truncate(value: str, limit: int = EMBED_FIELD_LIMIT) -> str:
    value = value or "없음"
    if len(value) <= limit:
        return value
    return value[: limit - 3] + "..."


def _status(title: str, details: str) -> tuple[str, str]:
    text = f"{title} {details}"
    if any(keyword in text for keyword in FAILURE_KEYWORDS):
        return "failure", "실패"
    if any(keyword in text for keyword in WARNING_KEYWORDS):
        return "warning", "주의"
    return "success", "완료"


def log_embed(
    user: discord.User | discord.Member,
    command_name: str,
    details: str = "",
    category: str = "command",
) -> discord.Embed:
    """유저가 명령어를 실행했을 때의 로그 Embed."""
    label = LOG_CATEGORY_LABELS.get(category, LOG_CATEGORY_LABELS["command"])
    status, status_label = _status(command_name, details)
    embed = discord.Embed(
        title=f"{command_name} · {status_label}",
        color=LOG_STATUS_COLORS[status],
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(name="사용자", value=_truncate(f"{user} (`{user.id}`)"), inline=False)
    embed.add_field(name="분류", value=label, inline=True)
    embed.add_field(name="상태", value=status_label, inline=True)
    if isinstance(user, discord.Member):
        embed.add_field(name="서버", value=_truncate(user.guild.name), inline=True)
    embed.add_field(name="세부사항", value=_truncate(details), inline=False)
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.set_footer(text=f"{label} 로그")
    return embed


def system_log_embed(title: str, details: str = "", category: str = "system") -> discord.Embed:
    """특정 유저 없이 봇이 자동으로 수행한 동작의 로그 Embed."""
    label = LOG_CATEGORY_LABELS.get(category, LOG_CATEGORY_LABELS["system"])
    status, status_label = _status(title, details)
    embed = discord.Embed(
        title=f"{title} · {status_label}",
        color=LOG_STATUS_COLORS[status],
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(name="분류", value=label, inline=True)
    embed.add_field(name="상태", value=status_label, inline=True)
    embed.add_field(name="세부사항", value=_truncate(details), inline=False)
    embed.set_footer(text=f"시스템 자동 실행 · {label} 로그")
    return embed
