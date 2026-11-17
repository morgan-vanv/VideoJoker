"""The raffle card: one embed that the bot posts when a raffle starts, then edits when it's drawn or cancelled. It
needs no connection to Discord to build, so tests/test_raffle.py looks at every version of it.

Mentions inside an embed show as names but never ping anyone, so the card can name the host and winners freely.
"""

from datetime import datetime

import discord

from raffle import lines

COLOUR = discord.Colour.gold()
COLOUR_DONE = discord.Colour.dark_grey()


def mention(user_id: int) -> str:
    return f"<@{user_id}>"


def running(prize: str, host_id: int, winners: int, ends_at: datetime) -> discord.Embed:
    text = [
        lines.PRIZE_LINE.format(prize=lines.prize(prize)),
        lines.ENTER,
        lines.ENDS.format(relative=lines.stamp(ends_at, "R"), at=lines.stamp(ends_at, "f")),
        lines.HOSTED.format(host=mention(host_id), winners=lines.winner_count(winners)),
    ]
    return discord.Embed(title=lines.TITLE_RUNNING, description="\n".join(text), colour=COLOUR)


def over(prize: str, host_id: int, winner_ids: list[int], entries: int, ended_at: datetime) -> discord.Embed:
    text = [lines.PRIZE_LINE.format(prize=lines.prize(prize))]
    if winner_ids:
        line = lines.WINNER if len(winner_ids) == 1 else lines.WINNERS
        text.append(line.format(winners=lines.names([mention(user_id) for user_id in winner_ids])))
        entry_line = lines.ONE_ENTRY if entries == 1 else lines.ENTRIES
        text.append(entry_line.format(count=entries, at=lines.stamp(ended_at, "f")))
    else:
        text.append(lines.NO_ENTRIES)
    text.append(lines.HOSTED_PLAIN.format(host=mention(host_id)))
    return discord.Embed(title=lines.TITLE_OVER, description="\n".join(text), colour=COLOUR_DONE)


def cancelled(prize: str, host_id: int, cancelled_by: int) -> discord.Embed:
    text = [
        lines.PRIZE_LINE.format(prize=lines.prize(prize)),
        lines.CANCELLED_BY.format(who=mention(cancelled_by)),
        lines.HOSTED_PLAIN.format(host=mention(host_id)),
    ]
    return discord.Embed(title=lines.TITLE_CANCELLED, description="\n".join(text), colour=COLOUR_DONE)


def won_message(prize: str, winner_ids: list[int]) -> str:
    """Posted under the card when it's drawn. Only the winners get pinged (the cog passes them as the only allowed
    mentions)."""
    if not winner_ids:
        return lines.NOBODY_WON.format(prize=lines.prize(prize))
    return lines.WON.format(winners=lines.names([mention(user_id) for user_id in winner_ids]), prize=lines.prize(prize))
