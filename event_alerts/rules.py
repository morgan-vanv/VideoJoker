"""The rules for event alerts, with no Discord in them: when a reminder is due, and which edits to an event are worth
telling people about. Plain inputs only (times, numbers, words), so tests/test_event_alerts.py checks them all.

Discord's own events do the scheduling, the weekly repeats and the RSVPs ("Interested"). The bot only adds what
Discord doesn't: a heads-up before the start, and a word when the time or place changes or the event is cancelled.
"""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

# Minutes before the start: the day before, and an hour before. EVENT_ALERT_TIMES in .env can change them.
DEFAULT_REMINDERS = (24 * 60, 60)

# After an edit, wait this long for more edits before posting one notice (fixing a typo shouldn't ping anyone twice)
NOTICE_DELAY = timedelta(minutes=2)

# A message holds 2000 characters and a ping is about 22 of them, so past this many the rest are counted, not pinged
MAX_PINGS = 50

_TIME = re.compile(r"^(\d+)\s*([dhm])$")
_MINUTES_IN = {"d": 24 * 60, "h": 60, "m": 1}


def parse_reminders(text: str) -> tuple[int, ...]:
    """'24h, 1h, 15m' -> (1440, 60, 15): minutes before the start, biggest first. Raises ValueError if a part
    isn't a whole number followed by d, h or m."""
    minutes = set()
    for part in text.split(","):
        match = _TIME.match(part.strip().lower())
        if not match or int(match.group(1)) == 0:
            raise ValueError(f"can't read {part.strip()!r}: use something like 24h, 1h or 15m")
        minutes.add(int(match.group(1)) * _MINUTES_IN[match.group(2)])
    return tuple(sorted(minutes, reverse=True))


def describe_reminders(reminders: tuple[int, ...]) -> str:
    """(1440, 60, 15) -> '24h, 1h and 15m', for the setup reply."""
    parts = [f"{minutes // 60}h" if minutes % 60 == 0 else f"{minutes}m" for minutes in reminders]
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]


@dataclass(frozen=True)
class DueReminders:
    """What to do about an event's reminders right now."""

    send: Optional[int]  # the reminder to post now (minutes before the start), or None
    done: tuple[int, ...]  # every reminder to mark as handled, including any skipped


def due_reminders(
    start: datetime, now: datetime, reminders: tuple[int, ...], already_sent: set[int], armed_since: datetime
) -> DueReminders:
    """Which reminder to send now, if any.

    - A reminder is due once its time has come (start minus its minutes) and the event hasn't started.
    - If several are due at once (the bot was down, say), only the latest one is sent: nobody needs
      "tomorrow!" and "in an hour!" in the same minute. The others count as done.
    - armed_since is when the bot could first have known about this start time: when the event was made, or when
      it was moved. A reminder whose time had already passed by then is skipped quietly (make an event for
      tonight and nobody gets a "starts tomorrow" ping; a move already got its own notice).
    """
    if now >= start:
        return DueReminders(None, ())
    due = [
        minutes for minutes in reminders if minutes not in already_sent and start - timedelta(minutes=minutes) <= now
    ]
    fresh = [minutes for minutes in due if start - timedelta(minutes=minutes) >= armed_since]
    return DueReminders(min(fresh) if fresh else None, tuple(due))


class Change(Enum):
    """The kinds of edit worth a notice. Anything else (title, description, cover picture) stays quiet."""

    MOVED = "moved"
    NEW_PLACE = "new place"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class EventState:
    """The parts of a Discord event the notices care about. status is discord.py's name for it:
    'scheduled', 'active', 'completed' or 'canceled' (Discord's spelling)."""

    name: str
    start: datetime
    location: Optional[str]
    status: str


def change_worth_a_notice(before: EventState, after: Optional[EventState], now: datetime) -> Optional[Change]:
    """Compares an event from before a round of edits with how it ended up (None = deleted).

    now is when the edits began. Only an event that was still upcoming then gets a notice: once its time has
    come, Discord starts and ends it on its own, and a weekly event rolling on to next week is not a move.
    """
    if before.status != "scheduled" or before.start <= now:
        return None
    if after is None or after.status == "canceled":
        return Change.CANCELLED
    if after.status != "scheduled":
        return None  # started early by hand, say: Discord tells the Interested people itself
    if after.start != before.start:
        return Change.MOVED
    if (after.location or "") != (before.location or ""):
        return Change.NEW_PLACE
    return None


def ping_list(user_ids: set[int]) -> tuple[str, list[int]]:
    """'<@1> <@2> ...' for everyone marked Interested (at most MAX_PINGS, then '+N more'), and the ids it pings.
    Sorted so the order doesn't jump around between reminders."""
    ids = sorted(user_ids)
    shown = ids[:MAX_PINGS]
    text = " ".join(f"<@{user_id}>" for user_id in shown)
    if len(ids) > MAX_PINGS:
        text += f" +{len(ids) - MAX_PINGS} more"
    return text, shown
