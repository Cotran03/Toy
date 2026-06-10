from datetime import datetime, timedelta, timezone

import discord


def adjusted_timeout_duration(
    member: discord.Member,
    previous_duration: timedelta,
    new_duration: timedelta,
) -> timedelta:
    """Keep elapsed timeout time when moving to a shorter punishment."""
    timed_out_until = member.timed_out_until
    if timed_out_until is None:
        return new_duration

    remaining = max(
        timedelta(0),
        timed_out_until.astimezone(timezone.utc) - datetime.now(timezone.utc),
    )
    elapsed = max(timedelta(0), previous_duration - remaining)
    return max(timedelta(0), new_duration - elapsed)
