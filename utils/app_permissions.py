from collections.abc import Collection

import discord
from discord import app_commands

from config import USER_CREATOR
from utils.check_permission import has_any_role


class MissingAdminPermission(app_commands.CheckFailure):
    """Raised when a user bypasses Discord visibility settings without access."""


def creator_only():
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.id == USER_CREATOR:
            return True

        raise MissingAdminPermission

    return app_commands.check(predicate)


def any_role(role_ids: Collection[int]):
    allowed_role_ids = tuple(role_ids)

    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.id == USER_CREATOR:
            return True

        if isinstance(interaction.user, discord.Member) and has_any_role(interaction.user, allowed_role_ids):
            return True

        raise MissingAdminPermission

    return app_commands.check(predicate)
