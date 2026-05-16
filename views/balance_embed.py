# Imports
import discord

# Import Config
from config import STORE_ITEMS


def _get_role_label(guild: discord.Guild, role_id: int, fallback: str) -> str:
    role = guild.get_role(role_id)
    return role.name if role else fallback


def store_embed(guild: discord.Guild, balance: int, selected_role_id: int | None = None) -> discord.Embed:
    embed = discord.Embed(
        title="🛒 INS 상점",
        description="아래 역할 목록을 참고하여 드롭다운에서 역할을 선택한 뒤 구매 버튼을 눌러주세요.",
        color=0x57F287,
    )
    embed.add_field(name="현재 잔액", value=f"{balance} INS", inline=False)

    for role_id, item in STORE_ITEMS.items():
        label = _get_role_label(guild, role_id, item["label"])
        embed.add_field(
            name=f"{label} — {item['price']} INS",
            value=item["description"],
            inline=False,
        )

    if selected_role_id is not None:
        selected_label = _get_role_label(
            guild,
            selected_role_id,
            STORE_ITEMS[selected_role_id]["label"],
        )
        embed.set_footer(text=f"선택한 역할: {selected_label}")

    return embed


def store_purchase_result_embed(role_name: str, price: int, remaining_balance: int) -> discord.Embed:
    embed = discord.Embed(
        title="✅ 구매 완료",
        description=f"{role_name} 역할 구매에 성공했습니다.",
        color=0x5865F2,
    )
    embed.add_field(name="사용한 INS", value=f"{price} INS", inline=True)
    embed.add_field(name="남은 INS", value=f"{remaining_balance} INS", inline=True)
    embed.set_footer(text="역할이 정상적으로 부여되었는지 확인해주세요.")
    return embed


def store_purchase_failed_embed(role_name: str, price: int, current_balance: int) -> discord.Embed:
    return discord.Embed(
        title="❌ 잔액 부족",
        description=f"{role_name} 역할 구매에는 {price} INS가 필요하지만, 현재 잔액은 {current_balance} INS입니다.",
        color=0xED4245,
    )
