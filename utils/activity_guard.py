import discord


RESTORE_IN_PROGRESS_MESSAGE = "DB 복구 중입니다. 잠시 후 다시 시도해 주세요."


def is_restore_in_progress(bot) -> bool:
    return bool(getattr(bot, "database_restore_in_progress", False))


async def deny_interaction_during_restore(interaction: discord.Interaction, bot) -> bool:
    if not is_restore_in_progress(bot):
        return False

    if interaction.response.is_done():
        await interaction.followup.send(RESTORE_IN_PROGRESS_MESSAGE, ephemeral=True)
    else:
        await interaction.response.send_message(RESTORE_IN_PROGRESS_MESSAGE, ephemeral=True)
    return True
