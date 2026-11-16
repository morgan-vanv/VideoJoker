"""Tests for the Minecraft features: name rules and UUIDs, the server-list ping (against a fake server speaking the
real protocol), the account lookups (against fake Mojang and GeyserMC servers answering in their published shapes),
the welcome rule, the database, and a guard on the VJ's lines."""

import asyncio
import json
import re

import pytest
from aiohttp import ClientSession, web

from minecraft import lines, lookup
from minecraft.accounts import clean_name, floodgate_uuid, java_uuid
from minecraft.ping import PingFailed, ServerStatus, encode_varint, packet, parse_status, ping
from minecraft.rules import should_welcome, status_line
from tests.real_commands import build_bot, commands_by_name

# ---- names and UUIDs


def test_java_names():
    assert clean_name("  Notch ", "java") == "Notch"
    assert clean_name("steve_2009", "java") == "steve_2009"
    assert clean_name("has space", "java") is None
    assert clean_name("x" * 17, "java") is None
    assert clean_name("", "java") is None


def test_bedrock_gamertags_allow_spaces_and_drop_floodgates_dot():
    assert clean_name("Steve Mc", "bedrock") == "Steve Mc"
    assert clean_name(".Steve Mc", "bedrock") == "Steve Mc"  # as it shows in game
    assert clean_name("under_score", "bedrock") is None
    assert clean_name("x" * 17, "bedrock") is None


def test_uuids():
    assert java_uuid("069a79f444e94726a5befca90e38aaf5") == "069a79f4-44e9-4726-a5be-fca90e38aaf5"  # Notch
    # Floodgate: zeros first, then the XUID, as in GeyserMC's own docs example
    assert floodgate_uuid(2535432196048835) == "00000000-0000-0000-0009-01f64f65c7c3"


# ---- the server-list ping


def test_varints():
    assert encode_varint(0) == b"\x00"
    assert encode_varint(127) == b"\x7f"
    assert encode_varint(128) == b"\x80\x01"
    assert encode_varint(25565) == b"\xdd\xc7\x01"
    assert encode_varint(-1) == b"\xff\xff\xff\xff\x0f"  # negative numbers are always 5 bytes


def test_parse_status():
    text = json.dumps({"version": {"name": "Velocity 26.3"}, "players": {"online": 3, "max": 50}, "description": "x"})
    assert parse_status(text) == ServerStatus(3, 50, "Velocity 26.3")
    with pytest.raises(PingFailed):
        parse_status("not json")


async def fake_minecraft(answer: dict):
    """A tiny server that answers a status ping the way a real one does. Returns (server, its port)."""

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        await reader.read(1024)  # the handshake and the status request; a real server checks them, we don't
        data = json.dumps(answer).encode()
        writer.write(packet(0x00, encode_varint(len(data)) + data))
        await writer.drain()
        writer.close()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    return server, server.sockets[0].getsockname()[1]


async def test_ping_reads_a_real_shaped_answer():
    server, port = await fake_minecraft({"version": {"name": "Velocity"}, "players": {"online": 2, "max": 50}})
    async with server:
        assert await ping("127.0.0.1", port) == ServerStatus(2, 50, "Velocity")


async def test_ping_of_nothing_fails_cleanly():
    server = await asyncio.start_server(lambda r, w: None, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    server.close()
    await server.wait_closed()  # now nothing listens on that port
    with pytest.raises(PingFailed):
        await ping("127.0.0.1", port)


def test_status_lines():
    assert status_line(None) == lines.STATUS_DOWN
    assert status_line(ServerStatus(0, 50, "")) == lines.STATUS_UP_EMPTY
    assert "3/50" in status_line(ServerStatus(3, 50, ""))


# ---- the lookups, against fake Mojang and GeyserMC


@pytest.fixture(name="fake_apis")
async def fixture_fake_apis(monkeypatch):
    """Local stand-ins for Mojang and GeyserMC that answer like the real ones (status codes and JSON shapes)."""

    async def mojang(request: web.Request):
        if request.match_info["name"].lower() == "notch":
            return web.json_response({"id": "069a79f444e94726a5befca90e38aaf5", "name": "Notch"})
        return web.Response(status=404)

    async def xuid(request: web.Request):
        if request.match_info["gamertag"].lower() == "steve mc":
            return web.json_response({"xuid": 2535432196048835})
        return web.json_response({})  # GeyserMC's "no such gamertag": an empty object

    async def gamertag(_request: web.Request):
        return web.json_response({"gamertag": "Steve Mc"})

    async def down(_request: web.Request):
        return web.Response(status=503)

    app = web.Application()
    app.router.add_get("/mojang/{name}", mojang)
    app.router.add_get("/xuid/{gamertag}", xuid)
    app.router.add_get("/gamertag/{xuid}", gamertag)
    app.router.add_get("/down/{name}", down)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    base = f"http://127.0.0.1:{runner.addresses[0][1]}"
    monkeypatch.setattr(lookup, "MOJANG_PROFILE", base + "/mojang/{name}")
    monkeypatch.setattr(lookup, "GEYSER_XUID", base + "/xuid/{gamertag}")
    monkeypatch.setattr(lookup, "GEYSER_GAMERTAG", base + "/gamertag/{xuid}")
    async with ClientSession() as session:
        yield session, base
    await runner.cleanup()


async def test_java_lookup(fake_apis):
    session, _ = fake_apis
    assert await lookup.find(session, "NOTCH", "java") == lookup.Profile(
        "069a79f4-44e9-4726-a5be-fca90e38aaf5", "Notch"
    )
    assert await lookup.find(session, "nobody_here", "java") is None


async def test_bedrock_lookup_spells_the_gamertag_like_xbox(fake_apis):
    session, _ = fake_apis
    assert await lookup.find(session, "steve mc", "bedrock") == lookup.Profile(
        "00000000-0000-0000-0009-01f64f65c7c3", "Steve Mc"
    )
    assert await lookup.find(session, "Nobody", "bedrock") is None


async def test_a_service_that_is_down_is_not_no_such_account(fake_apis, monkeypatch):
    session, base = fake_apis
    monkeypatch.setattr(lookup, "MOJANG_PROFILE", base + "/down/{name}")
    with pytest.raises(lookup.LookupUnavailable):
        await lookup.find(session, "Notch", "java")


# ---- the welcome rule

ROLE = 42


def test_welcome_when_the_role_arrives_after_the_gate():
    assert should_welcome(ROLE, [], [ROLE], before_pending=False, after_pending=False)


def test_no_welcome_while_still_at_the_join_gate():
    assert not should_welcome(ROLE, [], [ROLE], before_pending=True, after_pending=True)


def test_welcome_when_someone_with_the_role_passes_the_gate():
    assert should_welcome(ROLE, [ROLE], [ROLE], before_pending=True, after_pending=False)


def test_no_welcome_for_other_changes():
    assert not should_welcome(ROLE, [ROLE], [ROLE, 7], before_pending=False, after_pending=False)  # another role
    assert not should_welcome(ROLE, [ROLE], [], before_pending=False, after_pending=False)  # role taken away
    assert not should_welcome(ROLE, [], [7], before_pending=False, after_pending=False)


# ---- the database

NOTCH = "069a79f4-44e9-4726-a5be-fca90e38aaf5"
STEVE = "00000000-0000-0000-0009-01f64f65c7c3"


async def test_first_account_is_the_default_and_an_account_has_one_owner(db):
    assert await db.add_mc_account(1, "java", NOTCH, "Notch") is None
    assert await db.add_mc_account(1, "bedrock", STEVE, "Steve Mc") is None
    accounts = await db.get_mc_accounts(1)
    assert [(a.name, a.is_default) for a in accounts] == [("Notch", True), ("Steve Mc", False)]
    assert await db.add_mc_account(2, "java", NOTCH, "Notch") == 1  # someone else's already


async def test_relinking_your_own_account_refreshes_its_name(db):
    await db.add_mc_account(1, "java", NOTCH, "Notch")
    assert await db.add_mc_account(1, "java", NOTCH, "Notch2") == 1
    assert (await db.get_mc_accounts(1))[0].name == "Notch2"


async def test_find_by_name_ignores_case(db):
    await db.add_mc_account(1, "java", NOTCH, "Notch")
    assert [a.discord_id for a in await db.find_mc_accounts_by_name("notch")] == [1]
    assert not await db.find_mc_accounts_by_name("Herobrine")


async def test_remove_hands_the_default_on_and_default_switches(db):
    await db.add_mc_account(1, "java", NOTCH, "Notch")
    await db.add_mc_account(1, "bedrock", STEVE, "Steve Mc")
    assert await db.set_default_mc_account(1, STEVE)
    assert [a.uuid for a in await db.get_mc_accounts(1) if a.is_default] == [STEVE]
    assert await db.remove_mc_account(1, STEVE)
    assert [(a.uuid, a.is_default) for a in await db.get_mc_accounts(1)] == [(NOTCH, True)]
    assert not await db.remove_mc_account(2, NOTCH)  # not theirs
    assert not await db.set_default_mc_account(2, NOTCH)


async def test_settings_marquee_and_welcome_are_independent(db):
    await db.set_mc_marquee(10, 100, 1000)
    await db.set_mc_welcome(10, 200, 300)
    await db.set_mc_marquee(10, None, None)  # marquee off, welcome stays
    settings = (await db.get_mc_settings())[10]
    assert (settings.marquee_channel_id, settings.welcome_channel_id, settings.welcome_role_id) == (None, 200, 300)


async def test_welcomed_only_once(db):
    assert await db.mark_mc_welcomed(10, 1)
    assert not await db.mark_mc_welcomed(10, 1)
    assert await db.mark_mc_welcomed(11, 1)  # another server is another welcome


# ---- the guard: the VJ's Minecraft lines only point at Discord commands that exist

IN_GAME_COMMANDS = {"server"}  # "/server factions" is typed in Minecraft, not Discord
MENTION = re.compile(r"(?<![\w:/])/([a-z0-9][\w-]*)(?: ([a-z0-9][\w-]*))?")


def every_line() -> list[str]:
    texts = []
    for name, value in vars(lines).items():
        if name.startswith("__"):
            continue
        if isinstance(value, str):
            texts.append(value)
        elif isinstance(value, dict):
            texts += [text for text in value.values() if isinstance(text, str)]
    return texts


async def test_lines_only_mention_commands_that_exist():
    real = commands_by_name(build_bot())
    mentions = [match for text in every_line() for match in MENTION.findall(text)]
    assert len(mentions) >= 5
    for first, second in mentions:
        if first in IN_GAME_COMMANDS:
            continue
        assert f"{first} {second}" in real or first in real, f"/{first} {second} isn't a command"
