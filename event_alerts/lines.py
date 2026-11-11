"""The VJ's lines for event alerts. Every user-facing line lives here, so the voice stays in one place.

{name} is the event's own title, so the same lines fit a raid night and a game session. Times are Discord time
stamps (<t:...>): every reader sees them in their own time zone, and the R style counts down ("in 2 hours").
"""

import random
from datetime import datetime

import discord


def when(start: datetime) -> str:
    """'in 2 hours (Wednesday, November 18, 2026 6:45 PM)', shown in each reader's own time zone."""
    stamp = int(start.timestamp())
    return f"<t:{stamp}:R> (<t:{stamp}:F>)"


def title(name: str) -> str:
    """The event's name in bold, with any * or _ in it shown as typed instead of turning into formatting."""
    return f"**{discord.utils.escape_markdown(name)}**"


REMINDERS = [
    "🎬 {name} starts {when}! The VJ is already threading the tape.",
    "🍿 Get your popcorn, comrades: {name} rolls {when}.",
    "📼 Your VJ says: {name}, {when}. Do not make the film wait!",
    "📽️ Lights going down soon! {name} starts {when}.",
]

COMING = "Coming: {pings}"
NOBODY_YET = "Nobody's clicked Interested yet. Empty cinema, comrades! Click it below if you're in."

MOVED = "⏩ Plot twist! {name} has moved. New time: {when}."
NEW_PLACE = "🗺️ {name} has a new location: {location}"
CANCELLED = "🚫 Bad news, comrades: {name} ({start}) is cancelled. The tape goes back in the box."


def reminder(name: str, start: datetime) -> str:
    return random.choice(REMINDERS).format(name=title(name), when=when(start))


def location_text(location: str) -> str:
    """A web address in <...> so Discord doesn't add a preview of the site under the notice."""
    return f"<{location}>" if location.startswith(("http://", "https://")) else location


# /seteventalerts replies (only the person who ran it sees them)
SET = (
    "📽️ Event alerts on! Before each of this server's Discord events ({times} before) I'll post in {channel} "
    "and ping everyone who clicked Interested. Changed times or places, and cancellations, get posted there too."
)
OFF = "📼 Event alerts off for this server. Discord still pings Interested people when an event starts."
CANT_POST = "🎞️ I can't post in {channel}, comrade: I need **{missing}** there. Fix that and try again."
