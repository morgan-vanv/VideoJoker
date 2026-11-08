"""The rules for personal voice channels, with no Discord in sight, so tests can check them directly.

Everything here works on plain things: names, numbers and IDs. The cog (cogs/personal_vc.py) turns Discord
objects into those, asks these functions what to do, and then does it.

How it works on the server: join the lobby voice channel and the bot makes you a channel and moves you in.
One channel per person; it's yours until the last person leaves, and then it's deleted. Each channel has one of
three modes, and your mode and guest list are remembered for the next time.
"""

from enum import StrEnum
from typing import Iterable, Optional

MAX_NAME_LENGTH = 100  # Discord's limit for a channel name
NAME_SUFFIX = "'s voice channel"
CREATE_COOLDOWN = 10.0  # seconds between two new channels for the same person (stops create/delete loops)
# A Discord dropdown holds at most 25 choices, and ➖ Remove shows the whole guest list in one dropdown
MAX_GUESTS = 25


class Mode(StrEnum):
    """The three modes. A StrEnum member is also a plain string (Mode.LOCKED == "locked"), which is what the
    database stores."""

    OPEN = "open"  # 🔓 anyone can see and join (the default: a normal channel)
    LOCKED = "locked"  # 🔒 everyone can see it; only guests can join. Whoever's inside stays.
    HIDDEN = "hidden"  # 👻 only guests can see it at all


def mode_from_db(value: Optional[str]) -> Mode:
    """Turns what the database saved into a Mode. Nothing saved yet, or something unknown: Open, the safe default."""
    try:
        return Mode(value)
    except ValueError:
        return Mode.OPEN


def channel_name(display_name: str) -> str:
    """The channel's name, like "Morgan's voice channel". display_name is the server nickname (or the username
    if there isn't one). Long names are cut so the whole thing fits Discord's 100 characters."""
    room = MAX_NAME_LENGTH - len(NAME_SUFFIX)
    return (display_name.strip() or "Someone")[:room] + NAME_SUFFIX


def cooldown_left(last_created: Optional[float], now: float, cooldown: float = CREATE_COOLDOWN) -> float:
    """Seconds this person still has to wait before the bot makes them another channel (0 = go ahead).
    The times are seconds from a clock that only goes forward (time.monotonic() in the cog)."""
    if last_created is None:
        return 0.0
    return max(0.0, last_created + cooldown - now)


def should_delete(humans_inside: int) -> bool:
    """A personal channel goes when the last person leaves. Bots don't count: a music bot alone in an empty
    channel would otherwise keep it around forever."""
    return humans_inside == 0


# ---- Permissions
#
# Discord decides who can see/join a channel from "overwrites": one entry per role or member, each permission
# set to allow (✅), deny (❌) or neutral (/, "let the roles decide"). The order Discord applies them in:
# @everyone first, then roles (an allow from any role wins over a deny from another), then members (they win).
#
# A personal channel starts as a copy of its category's overwrites (it's "synced"), and each mode is a layer on
# top of that. The layer only ever touches two permissions: View Channel and Connect.
#
# A layer is plain data: {role or member id: {"view_channel": True/False/None, "connect": ...}}, where True is
# allow, False is deny and None is neutral. A permission left out of the inner dict isn't touched.

Changes = dict[str, Optional[bool]]

LET_IN: Changes = {"view_channel": True, "connect": True}


def let_in_ids(mode: Mode, insiders: Iterable[int], guests: Iterable[int], present: Iterable[int]) -> set[int]:
    """Who gets an explicit allow for View Channel + Connect.

    Open: nobody, the category decides, like for any normal channel.
    Locked/Hidden: the insiders (the owner, the staff role, and the bot itself, or it couldn't manage its own
    channel), the guest list, and whoever is inside right now (so nobody gets kicked out; that one isn't saved).
    """
    if mode is Mode.OPEN:
        return set()
    return set(insiders) | set(guests) | set(present)


def mode_layer(mode: Mode, everyone_id: int, inherited_ids: Iterable[int], let_in: Iterable[int]) -> dict[int, Changes]:
    """The overwrites a mode puts on top of the category's.

    everyone_id: the @everyone role (its id is the server's id). inherited_ids: every role and member the
    category has an overwrite for. let_in: from let_in_ids().
    """
    if mode is Mode.OPEN:
        return {}
    if mode is Mode.LOCKED:
        closed: Changes = {"connect": False}  # everyone can still see it (as far as the category lets them)
    else:
        closed = {"view_channel": False, "connect": False}
    # Category overwrites that ALLOW connecting (say, a "members" role) would beat the @everyone deny, because a
    # role's allow wins. So every inherited overwrite goes neutral on the closed permissions...
    layer = {target: {permission: None for permission in closed} for target in inherited_ids if target != everyone_id}
    layer[everyone_id] = dict(closed)
    # ...and then the people who should get in are allowed in explicitly
    for target in let_in:
        layer[target] = dict(LET_IN)
    return layer
