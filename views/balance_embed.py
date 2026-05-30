import discord

from config import STORE_ITEMS


def _get_role_label(guild: discord.Guild, role_id: int, fallback: str) -> str:
    role = guild.get_role(role_id)
    return role.name if role else fallback


def store_embed(
    guild: discord.Guild,
    balance: int,
) -> discord.Embed:
    embed = discord.Embed(
        title="INS 상점",
        description="구매할 역할을 선택한 뒤 구매 버튼을 눌러주세요.",
        color=0x57F287,
    )
    embed.add_field(name="현재 잔액", value=f"{balance} INS", inline=False)

    for role_id, item in STORE_ITEMS.items():
        label = _get_role_label(guild, role_id, item["label"])
        embed.add_field(
            name=f"{label} · {item['price']} INS",
            value=item["description"],
            inline=False,
        )

    return embed


def reward_embed(
    *,
    claimed: bool,
    amount: int,
    balance: int,
    reward_streak: int,
    last_reward_date: str | None,
) -> discord.Embed:
    if claimed:
        embed = discord.Embed(
            title="일일 보상 수령 완료",
            description=f"오늘의 보상으로 {amount} INS를 받았습니다.",
            color=0x57F287,
        )
    else:
        embed = discord.Embed(
            title="이미 수령한 보상",
            description="오늘은 이미 보상을 받았습니다. 내일 다시 시도해 주세요.",
            color=0xFEE75C,
        )

    embed.add_field(name="현재 INS", value=f"{balance:,}", inline=True)
    embed.add_field(name="연속 출석 일수", value=f"{reward_streak}일", inline=True)
    embed.add_field(name="마지막 수령일", value=last_reward_date or "없음", inline=True)
    return embed


def store_purchase_result_embed(
    role_name: str,
    price: int,
    remaining_balance: int,
) -> discord.Embed:
    embed = discord.Embed(
        title="구매 완료",
        description=f"{role_name} 역할 구매에 성공했습니다.",
        color=0x5865F2,
    )
    embed.add_field(name="사용한 INS", value=f"{price} INS", inline=True)
    embed.add_field(name="남은 INS", value=f"{remaining_balance} INS", inline=True)
    embed.set_footer(text="역할이 정상적으로 부여되었는지 확인해주세요.")
    return embed


def store_purchase_failed_embed(
    title: str,
    description: str,
    role_name: str | None = None,
    price: int | None = None,
    current_balance: int | None = None,
) -> discord.Embed:
    embed = discord.Embed(
        title=title,
        description=description,
        color=0xED4245,
    )

    if role_name is not None:
        embed.add_field(name="역할", value=role_name, inline=True)
    if price is not None:
        embed.add_field(name="가격", value=f"{price} INS", inline=True)
    if current_balance is not None:
        embed.add_field(name="현재 잔액", value=f"{current_balance} INS", inline=True)

    return embed


def economy_admin_notice_embed(
    moderator: discord.User | discord.Member,
    member: discord.Member,
    action: str,
    amount_text: str,
    reason: str,
) -> discord.Embed:
    embed = discord.Embed(
        title="INS 관리자 처리",
        color=0x5865F2,
    )
    embed.add_field(name="처리자", value=f"{moderator.mention} (`{moderator.id}`)", inline=False)
    embed.add_field(name="대상", value=f"{member.mention} (`{member.id}`)", inline=False)
    embed.add_field(name="처리 내용", value=action, inline=True)
    embed.add_field(name="변동 INS", value=amount_text, inline=True)
    embed.add_field(name="사유", value=reason, inline=False)
    return embed
