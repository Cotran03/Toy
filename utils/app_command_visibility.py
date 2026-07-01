from collections.abc import Iterable, Sequence

import discord
from discord import app_commands

from config import (
    CLEAR_ROLES,
    GENERAL_ADMIN_ROLES,
    SYSTEM_ADMIN_ROLES,
    USER_ADMIN_ROLES,
    USER_CREATOR,
)


ROLE_PERMISSION_TYPE = discord.AppCommandPermissionType.role.value
USER_PERMISSION_TYPE = discord.AppCommandPermissionType.user.value

ROLE_VISIBLE_COMMANDS = {
    "warn": USER_ADMIN_ROLES,
    "balance": USER_ADMIN_ROLES,
    "discussion-moderation": USER_ADMIN_ROLES,
    "userinfo": USER_ADMIN_ROLES,
    "discussion-settings": SYSTEM_ADMIN_ROLES,
    "economy": SYSTEM_ADMIN_ROLES,
    "seteconomy": SYSTEM_ADMIN_ROLES,
    "cleanup": CLEAR_ROLES,
    "verify": GENERAL_ADMIN_ROLES,
}
CREATOR_ONLY_COMMANDS = {"database"}
PUBLIC_COMMANDS = {"reward", "store", "info", "ping", "end", "promote"}


def _unique_ids(values: Iterable[int]) -> list[int]:
    ids: list[int] = []
    seen: set[int] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ids.append(value)
    return ids


def _public_permissions(guild_id: int) -> list[dict[str, int | bool]]:
    return [{"id": guild_id, "type": ROLE_PERMISSION_TYPE, "permission": True}]


def _restricted_permissions(
    guild_id: int,
    *,
    role_ids: Sequence[int] = (),
    user_ids: Sequence[int] = (),
) -> list[dict[str, int | bool]]:
    permissions: list[dict[str, int | bool]] = [
        {"id": guild_id, "type": ROLE_PERMISSION_TYPE, "permission": False},
    ]

    for role_id in _unique_ids(role_ids):
        permissions.append({"id": role_id, "type": ROLE_PERMISSION_TYPE, "permission": True})

    for user_id in _unique_ids([*user_ids, USER_CREATOR]):
        permissions.append({"id": user_id, "type": USER_PERMISSION_TYPE, "permission": True})

    return permissions


def _permissions_for_command(command_name: str, guild_id: int) -> list[dict[str, int | bool]] | None:
    if command_name in ROLE_VISIBLE_COMMANDS:
        return _restricted_permissions(guild_id, role_ids=ROLE_VISIBLE_COMMANDS[command_name])

    if command_name in CREATOR_ONLY_COMMANDS:
        return _restricted_permissions(guild_id, user_ids=[USER_CREATOR])

    if command_name in PUBLIC_COMMANDS:
        return _public_permissions(guild_id)

    return None


async def apply_app_command_visibility(
    guild: discord.abc.Snowflake,
    commands: Sequence[app_commands.AppCommand],
) -> tuple[list[str], list[str]]:
    """Apply guild command visibility by role/user after syncing commands."""
    applied: list[str] = []
    failures: list[str] = []

    for command in commands:
        permissions = _permissions_for_command(command.name, guild.id)
        if permissions is None:
            continue

        try:
            await command._state.http.edit_application_command_permissions(
                command.application_id,
                guild.id,
                command.id,
                {"permissions": permissions},
            )
        except discord.HTTPException as exc:
            failures.append(f"/{command.name}: {type(exc).__name__} / {exc}")
            continue

        applied.append(command.name)

    return applied, failures
