"""Tests for event alerts: the rules (event_alerts/rules.py), the reminder-times setting (cogs/event_alerts.py) and
the storage (core/database.py). Times are made up; ids are fake."""

from datetime import datetime, timedelta, timezone

import pytest

from cogs.event_alerts import reminders_from_env
from event_alerts import lines
from event_alerts.rules import (
    DEFAULT_REMINDERS,
    MAX_PINGS,
    Change,
    EventState,
    change_worth_a_notice,
    describe_reminders,
    due_reminders,
    parse_reminders,
    ping_list,
)

# A Wednesday game night at 6:45 pm New York time (23:45 UTC in November)
START = datetime(2026, 11, 18, 23, 45, tzinfo=timezone.utc)
MADE = START - timedelta(days=7)  # the event was made a week ahead
DAY, HOUR = 24 * 60, 60


def at(minutes_before: int) -> datetime:
    return START - timedelta(minutes=minutes_before)


# ---- The reminder times setting


def test_reminder_times_are_read_biggest_first():
    assert parse_reminders("1h, 24h,15m") == (DAY, HOUR, 15)
    assert parse_reminders("2d") == (2 * DAY,)


@pytest.mark.parametrize("text", ["", "soon", "1 hour", "0h", "1h,,2h", "-1h"])
def test_unreadable_reminder_times_are_refused(text):
    with pytest.raises(ValueError):
        parse_reminders(text)


def test_reminder_times_read_back_nicely():
    assert describe_reminders((DAY, HOUR)) == "24h and 1h"
    assert describe_reminders((DAY, HOUR, 15)) == "24h, 1h and 15m"
    assert describe_reminders((90,)) == "90m"


def test_no_setting_means_the_defaults(monkeypatch):
    monkeypatch.delenv("EVENT_ALERT_TIMES", raising=False)
    assert reminders_from_env() == DEFAULT_REMINDERS == (DAY, HOUR)


def test_a_typo_in_the_setting_falls_back_to_the_defaults(monkeypatch):
    monkeypatch.setenv("EVENT_ALERT_TIMES", "24 hours")
    assert reminders_from_env() == DEFAULT_REMINDERS


def test_the_setting_is_used_when_it_reads(monkeypatch):
    monkeypatch.setenv("EVENT_ALERT_TIMES", "5m,2m")
    assert reminders_from_env() == (5, 2)


# ---- Which reminder is due


def test_nothing_is_due_too_early():
    due = due_reminders(START, at(DAY + 1), DEFAULT_REMINDERS, set(), MADE)
    assert due.send is None and due.done == ()


def test_the_day_before_reminder_goes_out_on_time():
    due = due_reminders(START, at(DAY), DEFAULT_REMINDERS, set(), MADE)
    assert due.send == DAY and due.done == (DAY,)


def test_a_sent_reminder_is_not_sent_again():
    due = due_reminders(START, at(DAY - 5), DEFAULT_REMINDERS, {DAY}, MADE)
    assert due.send is None and due.done == ()


def test_the_hour_before_reminder_follows():
    due = due_reminders(START, at(HOUR), DEFAULT_REMINDERS, {DAY}, MADE)
    assert due.send == HOUR and due.done == (HOUR,)


def test_after_downtime_only_the_latest_reminder_goes_out():
    # The bot was down for both: only "in 30 minutes" is sent, and the day-before one is done too
    due = due_reminders(START, at(30), DEFAULT_REMINDERS, set(), MADE)
    assert due.send == HOUR and set(due.done) == {DAY, HOUR}


def test_nothing_once_the_event_has_started():
    due = due_reminders(START, START, DEFAULT_REMINDERS, set(), MADE)
    assert due.send is None and due.done == ()


def test_an_event_made_for_tonight_gets_no_starts_tomorrow_ping():
    made = at(5 * HOUR)  # made five hours ahead: the day-before reminder's time had already passed
    due = due_reminders(START, at(5 * HOUR - 1), DEFAULT_REMINDERS, set(), made)
    assert due.send is None and due.done == (DAY,)
    # ...but its hour-before reminder still comes
    assert due_reminders(START, at(HOUR), DEFAULT_REMINDERS, {DAY}, made).send == HOUR


def test_an_event_made_at_the_last_minute_gets_no_reminders():
    made = at(20)
    due = due_reminders(START, at(19), DEFAULT_REMINDERS, set(), made)
    assert due.send is None and set(due.done) == {DAY, HOUR}


def test_a_moved_event_skips_the_reminders_its_notice_covers():
    # How settle() uses it after a move: armed from now, so everything already due is marked done, nothing sent
    now = at(3 * HOUR)
    due = due_reminders(START, now, DEFAULT_REMINDERS, set(), armed_since=now)
    assert due.send is None and due.done == (DAY,)


# ---- Which edits get a notice

BEFORE = EventState("VtM: Night 12", START, "https://vtt.morganvanv.com", "scheduled")
EDITED_AT = START - timedelta(days=2)


def edited(**changes) -> EventState:
    fields = {"name": BEFORE.name, "start": BEFORE.start, "location": BEFORE.location, "status": BEFORE.status}
    return EventState(**(fields | changes))


def test_a_new_time_is_a_move():
    later = edited(start=START + timedelta(hours=1))
    assert change_worth_a_notice(BEFORE, later, EDITED_AT) is Change.MOVED


def test_a_new_location_gets_a_notice():
    assert change_worth_a_notice(BEFORE, edited(location="the usual Discord voice"), EDITED_AT) is Change.NEW_PLACE


@pytest.mark.parametrize("after", [None, edited(status="canceled")])
def test_cancelling_or_deleting_is_a_cancellation(after):
    assert change_worth_a_notice(BEFORE, after, EDITED_AT) is Change.CANCELLED


def test_title_and_description_edits_stay_quiet():
    assert change_worth_a_notice(BEFORE, edited(name="VtM: Night 12 (the debrief)"), EDITED_AT) is None
    assert change_worth_a_notice(BEFORE, edited(), EDITED_AT) is None  # e.g. only the description changed


def test_starting_and_ending_stay_quiet():
    # Discord starts external events by itself and tells Interested people; the bot has nothing to add
    assert change_worth_a_notice(BEFORE, edited(status="active"), START) is None
    running = edited(status="active")
    assert change_worth_a_notice(running, edited(status="completed"), START + timedelta(hours=2)) is None


def test_a_weekly_event_rolling_on_is_not_a_move():
    # After this week's session its time is in the past; next week's start showing up is the repeat, not a move
    next_week = edited(start=START + timedelta(days=7))
    assert change_worth_a_notice(BEFORE, next_week, START + timedelta(hours=2)) is None


def test_deleting_an_old_event_stays_quiet():
    assert change_worth_a_notice(edited(status="completed"), None, START + timedelta(days=1)) is None


# ---- Pings and wording


def test_pings_everyone_interested_in_a_steady_order():
    text, pinged = ping_list({30, 10, 20})
    assert text == "<@10> <@20> <@30>" and pinged == [10, 20, 30]


def test_nobody_interested_pings_nobody():
    assert ping_list(set()) == ("", [])


def test_a_huge_crowd_is_counted_not_all_pinged():
    text, pinged = ping_list(set(range(1, MAX_PINGS + 6)))
    assert len(pinged) == MAX_PINGS and text.endswith("+5 more")


def test_every_reminder_line_names_the_event_and_the_time():
    for line in lines.REMINDERS:
        text = line.format(name=lines.title("Night 12"), when=lines.when(START))
        assert "**Night 12**" in text and f"<t:{int(START.timestamp())}:R>" in text


def test_event_names_cant_break_the_formatting():
    assert lines.title("*secret* night") == "**\\*secret\\* night**"


def test_web_locations_get_no_preview():
    assert lines.location_text("https://vtt.morganvanv.com") == "<https://vtt.morganvanv.com>"
    assert lines.location_text("Morgan's basement") == "Morgan's basement"


# ---- Storage


async def test_alert_channels_are_saved_and_cleared(db):
    assert await db.get_event_alert_channels() == {}
    await db.set_event_alert_channel(1, 100)
    await db.set_event_alert_channel(2, 200)
    await db.set_event_alert_channel(1, 101)  # picking a new channel replaces the old one
    assert await db.get_event_alert_channels() == {1: 101, 2: 200}
    await db.clear_event_alert_channel(1)
    assert await db.get_event_alert_channels() == {2: 200}


async def test_sent_reminders_are_remembered_per_start_time(db):
    await db.mark_event_reminders_sent(7, 1000, [DAY])
    await db.mark_event_reminders_sent(7, 1000, [DAY, HOUR])  # marking one twice is fine
    assert await db.get_sent_event_reminders(7, 1000) == {DAY, HOUR}
    assert await db.get_sent_event_reminders(7, 2000) == set()  # moved, or next week: a fresh start


async def test_old_reminder_records_are_forgotten(db):
    await db.mark_event_reminders_sent(7, 1000, [HOUR])
    await db.mark_event_reminders_sent(8, 5000, [HOUR])
    await db.forget_event_reminders_before(3000)
    assert await db.get_sent_event_reminders(7, 1000) == set()
    assert await db.get_sent_event_reminders(8, 5000) == {HOUR}
