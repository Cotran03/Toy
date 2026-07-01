from collections.abc import Collection

import discord
from discord import app_commands

from config import GENERAL_ADMIN_ROLES, SYSTEM_ADMIN_ROLES, USER_ADMIN_ROLES, USER_CREATOR
from utils.check_permission import has_any_role


class MissingAdminPermission(app_commands.CheckFailure):
    """Raised when a user bypasses Discord visibility settings without access."""


ROLE_PERMISSION_FALLBACKS = {
    tuple(USER_ADMIN_ROLES): ("manage_messages",),
    tuple(SYSTEM_ADMIN_ROLES): ("manage_channels",),
    tuple(GENERAL_ADMIN_ROLES): ("mention_everyone",),
}


def has_required_permissions(member: discord.Member, role_ids: tuple[int, ...]) -> bool:
    permission_names = ROLE_PERMISSION_FALLBACKS.get(role_ids, ())
    permissions = member.guild_permissions
    return bool(permission_names) and all(getattr(permissions, name, False) for name in permission_names)


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

        if isinstance(interaction.user, discord.Member):
            if has_any_role(interaction.user, allowed_role_ids):
                return True

            if has_required_permissions(interaction.user, allowed_role_ids):
                return True

        raise MissingAdminPermission

    return app_commands.check(predicate)
