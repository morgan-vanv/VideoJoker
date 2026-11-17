"""Tests for the bot's side of the booth: shout rules, postcard wording, the database bits, and the bot's client
talking to the real booth app (with fake game consoles behind it), end to end."""

import pytest
from aiohttp import ClientSession
from aiohttp.test_utils import TestServer

from booth.app import Booth, make_app
from minecraft import lines, postcards
from minecraft.booth import BoothClient, BoothUnavailable, ModeStatus
from minecraft.shout import EVERYONE_SECONDS, PER_PERSON_SECONDS, Cooldowns
from tests.test_booth import NOTCH, TOKEN, FakeServers, config

# ---- shout rules


def test_cooldowns():
    cooldowns = Cooldowns()
    assert cooldowns.check(1, 1000) is None
    cooldowns.shouted(1, 1000)
    assert cooldowns.check(1, 1001) == (1000 + PER_PERSON_SECONDS, False)  # their own rest
    assert cooldowns.check(2, 1001) == (1000 + EVERYONE_SECONDS, True)  # someone else just shouted
    assert cooldowns.check(2, 1000 + EVERYONE_SECONDS) is None
    assert cooldowns.check(1, 1000 + PER_PERSON_SECONDS) is None


# ---- postcards


def test_account_name_tells_bedrock_by_its_dot():
    assert postcards.account_name(".Steve Mc") == ("bedrock", "Steve Mc")
    assert postcards.account_name("Notch") == ("java", "Notch")


def test_postcard_texts():
    assert postcards.text_for({"kind": "join", "name": "Notch"}, []) == lines.POSTCARD_JOIN.format(name="Notch")
    death = postcards.text_for({"kind": "death", "name": "Notch", "text": "Notch drowned"}, [7])
    assert death == "💀 Notch drowned. (<@7>)"
    advancement = postcards.text_for({"kind": "advancement", "name": "Not_ch", "title": "Stone Age"}, [])
    assert advancement == "🏆 **Not\\_ch** unlocked **Stone Age**."  # markdown in names is escaped
    assert postcards.text_for({"kind": "chat", "name": "Notch"}, []) is None
    assert postcards.text_for({"kind": "death", "name": "Notch"}, []) is None  # no text, no postcard


# ---- the database


async def test_shout_money_goes_to_the_bank_and_back(db):
    await db.add_balance(1, 60)
    assert await db.move_ush_with_bank(1, 50, "shout", True, 99)
    assert await db.get_balance(1) == 10
    assert not await db.move_ush_with_bank(1, 50, "shout", True, 99)  # can't afford a second one
    assert await db.move_ush_with_bank(1, 50, "shout refund", False, 99)
    assert await db.get_balance(1) == 60
    moves = await db.get_recent_ush_moves(1)
    assert [(m.from_user_id, m.to_user_id, m.kind) for m in moves][:2] == [
        (None, 1, "shout refund"),
        (1, None, "shout"),
    ]
    assert not await db.move_ush_with_bank(1, 0, "shout", True, 99)


async def test_postcards_settings_and_first_sightings(db):
    await db.set_mc_postcards(10, 100)
    assert await db.get_mc_postcards() == {10: 100}
    await db.set_mc_postcards(10, None)
    assert await db.get_mc_postcards() == {}
    assert await db.mark_mc_player_seen("notch")
    assert not await db.mark_mc_player_seen("notch")


async def test_all_linked_uuids(db):
    await db.add_mc_account(1, "java", NOTCH, "Notch")
    assert await db.get_all_mc_uuids() == [NOTCH]


# ---- the bot's client against the real booth app


@pytest.fixture(name="client_and_servers")
async def fixture_client_and_servers():
    servers = FakeServers()
    booth = Booth(config(), rcon_runner=servers)
    server = TestServer(make_app(booth, run_jobs=False))
    await server.start_server()
    async with ClientSession() as session:
        yield BoothClient(session, str(server.make_url("/")), TOKEN), booth, servers
    await server.close()


async def test_client_end_to_end(client_and_servers):
    client, booth, servers = client_and_servers
    servers.asleep.add("anarchy")
    servers.online["factions"] = {"Notch": NOTCH}

    assert await client.status() == {"factions": ModeStatus(True, 1), "anarchy": ModeStatus(False, 0)}
    result = await client.shout("Mo", "hello")
    assert result.heard == ["factions"] and result.asleep == ["anarchy"]
    await client.put_linked([NOTCH])
    assert booth.linked == {NOTCH}

    booth.add_event("join", "Notch")
    cards = await client.postcards(0)
    assert cards.boot == booth.boot and cards.latest == 1 and cards.events[0]["name"] == "Notch"
    assert (await client.postcards(1)).events == []


async def test_client_with_a_wrong_token_gets_nothing(client_and_servers):
    client, _, _ = client_and_servers
    client.headers = {"Authorization": "Bearer wrong"}
    with pytest.raises(BoothUnavailable):
        await client.status()


async def test_client_when_the_booth_is_down():
    async with ClientSession() as session:
        with pytest.raises(BoothUnavailable):
            await BoothClient(session, "http://127.0.0.1:9", TOKEN).status()
