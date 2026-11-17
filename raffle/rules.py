"""The rules for raffles, with no Discord in them: how long a raffle can run, which reaction counts as a ticket, who
can win, and the draw itself. Plain inputs only (words, numbers, user ids), so tests/test_raffle.py checks them all.
"""

import random
import re
from datetime import timedelta
from typing import Iterable

# The reaction people click to enter. The bot adds the first one itself, so everyone can see where to click.
TICKET = "🎟️"

SHORTEST = timedelta(minutes=1)
LONGEST = timedelta(days=7)
MOST_WINNERS = 5

# "2h", "30m", "1d 12h", "1h30m": one or more whole numbers, each followed by d, h or m
_WHOLE = re.compile(r"^(?:\d+\s*[dhm]\s*)+$")
_PART = re.compile(r"(\d+)\s*([dhm])")
_UNIT = {"d": timedelta(days=1), "h": timedelta(hours=1), "m": timedelta(minutes=1)}


def parse_duration(text: str) -> timedelta:
    """'2h' -> 2 hours, '1d 12h' -> a day and a half. Raises ValueError if it isn't written that way, or is shorter
    than SHORTEST or longer than LONGEST (the message says which, for the person who typed it)."""
    cleaned = text.strip().lower()
    if not _WHOLE.match(cleaned):
        raise ValueError("format")
    duration = sum((int(number) * _UNIT[unit] for number, unit in _PART.findall(cleaned)), timedelta())
    if duration < SHORTEST:
        raise ValueError("too short")
    if duration > LONGEST:
        raise ValueError("too long")
    return duration


def is_ticket(emoji) -> bool:
    """True if this reaction is the ticket. The ticket emoji can come back from Discord with or without the invisible
    "show as emoji" character (U+FE0F) on the end, so both count. Custom server emojis never match."""
    return str(emoji).replace("️", "") == TICKET.replace("️", "")


def eligible(entrants: Iterable[int], host_id: int, banned: set[int]) -> list[int]:
    """Who's really in the draw: everyone who reacted, once each, except the host (no winning your own raffle) and
    banned users. Bots are left out before this, where the bot can still see who's a bot."""
    return sorted({user_id for user_id in entrants if user_id != host_id and user_id not in banned})


def pick_winners(entries: list[int], count: int, rng: random.Random | None = None) -> list[int]:
    """Draws up to `count` different winners from the entries (fewer if fewer people entered).

    rng: tests pass a seeded one to get the same draw every time. The real draw uses SystemRandom, which picks from
    the operating system's randomness instead of a sequence someone could work out.
    """
    rng = rng or random.SystemRandom()
    return rng.sample(entries, min(count, len(entries)))
