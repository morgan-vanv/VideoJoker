"""Every line event alerts post, kept in one place.

Plain and clear on purpose (Morgan, 2026-11-11): these are schedule notices people skim, so no flavour text. Each
post is a short headline, a small grey line with the pings, then the event's link (Discord shows it as the event
card: title, date, location and the Interested button), so the headline doesn't repeat what the card shows.

{name} is the event's own title, so the same lines fit a raid night and a game session. Times are Discord time
stamps (<t:...>): every reader sees them in their own time zone. R counts down ("in 2 hours"); f is the short
date and time ("November 18, 2026 6:45 PM").
"""

from datetime import datetime

import discord


def stamp(start: datetime, style: str) -> str:
    return f"<t:{int(start.timestamp())}:{style}>"


def title(name: str) -> str:
    """The event's name in bold, with any * or _ in it shown as typed instead of turning into formatting."""
    return f"**{discord.utils.escape_markdown(name)}**"


REMINDER = "⏰ {name} starts {relative} ({at})"
MOVED = "🔁 {name} has moved to {at} ({relative})"
NEW_PLACE = "📍 {name} has a new location: {location}"
CANCELLED = "❌ {name} on {at} is cancelled"

# "-#" is Discord's small grey subtext; the pings in it still notify people
INTERESTED = "-# Interested: {pings}"
NOBODY_YET = "-# No one has marked Interested yet."


def reminder(name: str, start: datetime) -> str:
    return REMINDER.format(name=title(name), relative=stamp(start, "R"), at=stamp(start, "f"))


def moved(name: str, start: datetime) -> str:
    return MOVED.format(name=title(name), at=stamp(start, "f"), relative=stamp(start, "R"))


def new_place(name: str, location: str) -> str:
    # A web address goes in <...> so Discord doesn't add a preview of that site under the event card
    shown = f"<{location}>" if location.startswith(("http://", "https://")) else location
    return NEW_PLACE.format(name=title(name), location=shown)


def cancelled(name: str, start: datetime) -> str:
    return CANCELLED.format(name=title(name), at=stamp(start, "f"))


def message(headline: str, pings: str, link: str = "", nobody_line: str = "") -> str:
    """Headline, then the Interested line (or nobody_line when no one is), then the event link."""
    who = INTERESTED.format(pings=pings) if pings else nobody_line
    return "\n".join(part for part in (headline, who, link) if part)


# /seteventalerts replies (only the person who ran it sees them)
SET = (
    "Event alerts are on. I'll post in {channel} {times} before each of this server's events, pinging everyone "
    "marked Interested, and when an event's time or location changes or it's cancelled."
)
OFF = "Event alerts are off for this server. Discord still notifies Interested people when an event starts."
CANT_POST = "I can't post in {channel}. I need **{missing}** there."
