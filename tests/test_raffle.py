"""Tests for raffles: the rules (raffle/rules.py), the card (raffle/card.py), the storage (core/database.py), and the
draw itself (cogs/raffle.py) against a stand-in for Discord. Ids and times are made up."""

import random
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import discord
import pytest

from cogs.raffle import Outcome, Raffle, missing
from raffle import card, lines
from raffle.rules import TICKET, eligible, is_ticket, parse_duration, pick_winners

HOST, ALICE, BOB, CARL, BANNED_DAN = 1, 2, 3, 4, 5
NOW = datetime(2026, 11, 16, 20, 0, tzinfo=timezone.utc)


# ---- How long a raffle runs


@pytest.mark.parametrize(
    "text, expected",
    [
        ("30m", timedelta(minutes=30)),
        ("2h", timedelta(hours=2)),
        ("1d", timedelta(days=1)),
        ("1d 12h", timedelta(days=1, hours=12)),
        ("1h30m", timedelta(hours=1, minutes=30)),
        (" 2H ", timedelta(hours=2)),
        ("1m", timedelta(minutes=1)),
        ("7d", timedelta(days=7)),
    ],
)
def test_durations_are_read(text, expected):
    assert parse_duration(text) == expected


@pytest.mark.parametrize("text", ["", "soon", "2 hours", "h", "1.5h", "-1h", "1w"])
def test_unreadable_durations_are_refused(text):
    with pytest.raises(ValueError, match="format"):
        parse_duration(text)


def test_durations_have_limits():
    with pytest.raises(ValueError, match="too short"):
        parse_duration("0m")
    with pytest.raises(ValueError, match="too long"):
        parse_duration("7d 1m")


# ---- The ticket, and who can win


def test_the_ticket_counts_with_or_without_the_invisible_emoji_character():
    assert is_ticket(TICKET)
    assert is_ticket("\U0001f39f")  # 🎟 without U+FE0F
    assert is_ticket("\U0001f39f️")
    assert not is_ticket("🎉")


def test_host_and_banned_users_cant_win_and_nobody_enters_twice():
    entries = eligible([ALICE, HOST, BOB, ALICE, BANNED_DAN], HOST, banned={BANNED_DAN})
    assert entries == [ALICE, BOB]


def test_the_draw_picks_different_winners_from_the_entries():
    entries = [ALICE, BOB, CARL]
    winners = pick_winners(entries, 2, random.Random(7))
    assert len(winners) == 2 and len(set(winners)) == 2 and set(winners) <= set(entries)


def test_fewer_entries_than_winners_means_everyone_wins():
    assert sorted(pick_winners([ALICE, BOB], 5)) == [ALICE, BOB]
    assert not pick_winners([], 1)


def test_everyone_can_win():
    seen = set()
    rng = random.Random(1)
    for _ in range(200):
        seen.update(pick_winners([ALICE, BOB, CARL], 1, rng))
    assert seen == {ALICE, BOB, CARL}


# ---- The card and the winner line


def test_names_read_like_a_sentence():
    assert lines.names(["@A"]) == "@A"
    assert lines.names(["@A", "@B"]) == "@A and @B"
    assert lines.names(["@A", "@B", "@C"]) == "@A, @B and @C"


def test_running_card_says_how_to_enter_and_when_it_ends():
    embed = card.running("Bond 50", HOST, 1, NOW)
    assert embed.title == lines.TITLE_RUNNING
    assert "**Bond 50**" in embed.description
    assert f"React with {TICKET} to enter." in embed.description
    assert f"<t:{int(NOW.timestamp())}:R>" in embed.description
    assert f"Hosted by <@{HOST}> · 1 winner" in embed.description
    assert "3 winners" in card.running("Bond 50", HOST, 3, NOW).description


def test_finished_card_names_the_winners():
    one = card.over("Bond 50", HOST, [ALICE], 1, NOW).description
    assert f"**Winner:** <@{ALICE}>" in one and "1 entry ·" in one
    two = card.over("Bond 50", HOST, [ALICE, BOB], 12, NOW).description
    assert f"**Winners:** <@{ALICE}> and <@{BOB}>" in two and "12 entries ·" in two
    assert lines.NO_ENTRIES in card.over("Bond 50", HOST, [], 0, NOW).description


def test_cancelled_card_says_who_cancelled_it():
    embed = card.cancelled("Bond 50", HOST, CARL)
    assert embed.title == lines.TITLE_CANCELLED
    assert f"Cancelled by <@{CARL}>." in embed.description


def test_winner_line_is_morgans_words():
    assert card.won_message("Bond 50", [ALICE]) == f"Congratulations <@{ALICE}> you just won: **Bond 50**"
    assert card.won_message("Bond 50", [ALICE, BOB]) == (
        f"Congratulations <@{ALICE}> and <@{BOB}> you just won: **Bond 50**"
    )
    assert card.won_message("Bond 50", []) == "No one entered the raffle for **Bond 50**, so there's no winner."


def test_prize_formatting_characters_show_as_typed():
    assert lines.prize("*rare* drop_") == "**\\*rare\\* drop\\_**"


def test_threads_need_send_messages_in_threads_instead():
    everything = discord.Permissions(
        view_channel=True, send_messages=True, embed_links=True, add_reactions=True, read_message_history=True
    )
    assert not missing(everything, in_thread=False)
    assert missing(everything, in_thread=True) == ["Send Messages in Threads"]
    assert missing(discord.Permissions.none(), in_thread=False) == [
        "View Channel",
        "Send Messages",
        "Embed Links",
        "Add Reactions",
        "Read Message History",
    ]


# ---- Storage


async def add(db, host=HOST, ends_at=1000, guild=10):
    return await db.add_raffle(guild, 20, 30 + host, host, "Bond 50", 1, ends_at)


async def test_a_raffle_is_saved_running(db):
    raffle_id = await add(db)
    raffle = await db.get_raffle(raffle_id)
    assert raffle.prize == "Bond 50" and raffle.state == "running" and raffle.winners == 1
    assert await db.get_hosts_raffle(10, HOST) == raffle
    assert await db.get_hosts_raffle(10, ALICE) is None
    assert await db.get_hosts_raffle(11, HOST) is None  # another server


async def test_only_raffles_whose_time_is_up_are_due(db):
    soon = await add(db, host=HOST, ends_at=1000)
    later = await add(db, host=ALICE, ends_at=5000)
    assert [raffle.id for raffle in await db.get_due_raffles(1000)] == [soon]
    assert [raffle.id for raffle in await db.get_due_raffles(9999)] == [soon, later]
    assert [raffle.id for raffle in await db.get_running_raffles(10)] == [soon, later]


async def test_a_raffle_closes_only_once(db):
    raffle_id = await add(db)
    assert await db.close_raffle(raffle_id, "drawn")
    assert not await db.close_raffle(raffle_id, "cancelled")  # someone else got there first
    assert (await db.get_raffle(raffle_id)).state == "drawn"
    assert not await db.get_due_raffles(9999)
    assert await db.get_hosts_raffle(10, HOST) is None  # free to start another


async def test_an_interrupted_draw_can_be_put_back(db):
    raffle_id = await add(db)
    await db.close_raffle(raffle_id, "drawn")
    await db.set_raffle_state(raffle_id, "running")
    assert [raffle.id for raffle in await db.get_due_raffles(9999)] == [raffle_id]


async def test_unknown_states_are_refused(db):
    with pytest.raises(ValueError):
        await db.close_raffle(1, "running")
    with pytest.raises(ValueError):
        await db.set_raffle_state(1, "paused")


# ---- The draw, against a stand-in for Discord


async def fake_users(users):
    """Stands in for reaction.users(): something to loop over with `async for`."""
    for user in users:
        yield user


class FakeMessage:
    def __init__(self, reactors, emoji=TICKET, fail_edit=None):
        users = [SimpleNamespace(id=user_id, bot=is_bot) for user_id, is_bot in reactors]
        self.reactions = [SimpleNamespace(emoji=emoji, users=lambda: fake_users(users))]
        self.fail_edit = fail_edit
        self.edited = None
        self.replies = []

    async def edit(self, embed):
        if self.fail_edit:
            raise self.fail_edit
        self.edited = embed

    async def reply(self, content, allowed_mentions):
        self.replies.append((content, allowed_mentions))


def http_error(kind, status):
    return kind(SimpleNamespace(status=status, reason="test"), "test")


def raffle_cog(db, message=None, fetch_error=None):
    async def fetch_message(_message_id):
        if fetch_error:
            raise fetch_error
        return message

    bot = SimpleNamespace(
        db=db, get_partial_messageable=lambda *_args, **_kwargs: SimpleNamespace(fetch_message=fetch_message)
    )
    return Raffle(bot)


async def test_the_draw_picks_a_real_entrant_and_pings_only_them(db):
    db.banned.add(BANNED_DAN)
    raffle = await db.get_raffle(await add(db))
    bot_user = 999
    message = FakeMessage([(bot_user, True), (HOST, False), (BANNED_DAN, False), (ALICE, False)])
    assert await raffle_cog(db, message).draw(raffle) is Outcome.DRAWN

    assert f"**Winner:** <@{ALICE}>" in message.edited.description
    content, mentions = message.replies[0]
    assert content == f"Congratulations <@{ALICE}> you just won: **Bond 50**"
    assert [user.id for user in mentions.users] == [ALICE]
    assert mentions.everyone is False and mentions.roles is False
    assert (await db.get_raffle(raffle.id)).state == "drawn"


async def test_no_entries_means_no_winner(db):
    raffle = await db.get_raffle(await add(db))
    message = FakeMessage([(HOST, False)])
    assert await raffle_cog(db, message).draw(raffle) is Outcome.DRAWN
    assert message.replies[0][0] == "No one entered the raffle for **Bond 50**, so there's no winner."
    assert not message.replies[0][1].users


async def test_other_reactions_dont_count(db):
    raffle = await db.get_raffle(await add(db))
    message = FakeMessage([(ALICE, False)], emoji="🎉")
    await raffle_cog(db, message).draw(raffle)
    assert lines.NO_ENTRIES in message.edited.description


async def test_a_raffle_is_only_drawn_once(db):
    raffle = await db.get_raffle(await add(db))
    cog = raffle_cog(db, FakeMessage([(ALICE, False)]))
    assert await cog.draw(raffle) is Outcome.DRAWN
    assert await cog.draw(raffle) is Outcome.NOT_RUNNING


async def test_a_deleted_card_closes_the_raffle(db):
    raffle = await db.get_raffle(await add(db))
    cog = raffle_cog(db, fetch_error=http_error(discord.NotFound, 404))
    assert await cog.draw(raffle) is Outcome.GONE
    assert (await db.get_raffle(raffle.id)).state == "cancelled"


async def test_a_discord_hiccup_puts_the_raffle_back_to_try_again(db):
    raffle = await db.get_raffle(await add(db))
    message = FakeMessage([(ALICE, False)], fail_edit=http_error(discord.HTTPException, 500))
    assert await raffle_cog(db, message).draw(raffle) is Outcome.TRY_AGAIN
    assert (await db.get_raffle(raffle.id)).state == "running"
    assert not message.replies  # nothing was announced
