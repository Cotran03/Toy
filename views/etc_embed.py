import discord


def info_embed(member: discord.Member, info: dict) -> discord.Embed:
    embed = discord.Embed(title="사용자 정보", color=0x95A5A6)
    embed.set_thumbnail(url=member.display_avatar.url)

    embed.add_field(name="닉네임", value=member.display_name, inline=True)
    embed.add_field(name="디스코드 태그", value=str(member), inline=True)
    embed.add_field(name="서버 가입일", value=info["joined_text"], inline=False)
    embed.add_field(name="가입 후 시간", value=info["elapsed_text"], inline=False)
    embed.add_field(name="보유 INS", value=f"{info['balance']:,}", inline=True)

    if info["is_advanced"]:
        embed.add_field(name="게시한 토론 수", value=str(info["post_count"]), inline=True)
        embed.add_field(name="진행 중 토론 수", value=str(info["active_post_count"]), inline=True)
        embed.add_field(name="종료한 토론 수", value=str(info["end_count"]), inline=True)
        embed.add_field(name="홍보 사용 수", value=str(info["total_promote_count"]), inline=True)
        embed.add_field(name="경고 잔여 수", value=str(info["warning_count"]), inline=True)
    else:
        embed.add_field(
            name="고급 정보",
            value="'정보보기' 역할이 있으면 더 많은 정보를 확인할 수 있습니다.",
            inline=False,
        )

    return embed
