# Imports
import discord

def has_any_role(member: discord.Member, role_ids: list[int]) -> bool:
    """멤버가 role_ids중 하나라도 보유하면 True"""
    return any(role.id in role_ids for role in member.roles)