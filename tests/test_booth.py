"""Tests for the booth (booth/): the RCON client against a fake console speaking the real protocol, the log readers
(including that a player's IP never comes out of them), the in-game messages, and the web service with its nudge."""

import asyncio
import json
import os
import struct

import pytest
from aiohttp.test_utils import TestClient, TestServer

from booth import game, logs, rcon
from booth.app import Booth, Config, make_app

TOKEN = "t" * 40
AUTH = {"Authorization": f"Bearer {TOKEN}"}
NOTCH = "069a79f4-44e9-4726-a5be-fca90e38aaf5"
BEDROCK = "00000000-0000-0000-0009-01f64f65c7c3"

# ---- RCON


async def fake_console(password: str, answer: str):
    """A server that speaks RCON: checks the password, answers any command with `answer`."""
    commands = []

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        request_id, _, given = await rcon.read_packet(reader)
        ok = given == password
        writer.write(rcon.encode(request_id if ok else -1, rcon.AUTH_RESPONSE, ""))
        if ok:
            request_id, _, command = await rcon.read_packet(reader)
            commands.append(command)
            writer.write(rcon.encode(request_id, rcon.RESPONSE, answer))
        await writer.drain()
        writer.close()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    return server, server.sockets[0].getsockname()[1], commands


def test_rcon_packet_shape():
    data = rcon.encode(7, rcon.COMMAND, "list")
    assert struct.unpack("<iii", data[:12]) == (14, 7, 2)  # length = 4 + 4 + 4 letters + 2 zero bytes
    assert data[12:] == b"list\x00\x00"


async def test_rcon_runs_a_command():
    server, port, commands = await fake_console("secret", "There are 0 of a max of 20 players online: ")
    async with server:
        answer = await rcon.run("127.0.0.1", port, "secret", "list uuids")
    assert answer.startswith("There are 0") and commands == ["list uuids"]


async def test_rcon_wrong_password_is_refused_not_asleep():
    server, port, _ = await fake_console("secret", "")
    async with server:
        with pytest.raises(rcon.RconRefused):
            await rcon.run("127.0.0.1", port, "wrong", "list")


async def test_rcon_to_a_sleeping_mode_is_unavailable():
    server = await asyncio.start_server(lambda r, w: None, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    server.close()
    await server.wait_closed()
    with pytest.raises(rcon.RconUnavailable):
        await rcon.run("127.0.0.1", port, "secret", "list")


# ---- what the booth says in game


def tellraw_json(command: str) -> list:
    """The JSON part of a tellraw command (after "tellraw <target> ")."""
    return json.loads(command.split(" ", 2)[2])


def test_parse_modes():
    assert game.parse_modes("factions=factions:25575, anarchy=anarchy:25575") == [
        game.Mode("factions", "factions", 25575),
        game.Mode("anarchy", "anarchy", 25575),
    ]
    with pytest.raises(ValueError):
        game.parse_modes("factions")
    with pytest.raises(ValueError):
        game.parse_modes("")


def test_shout_cannot_break_out_of_its_message():
    sneaky = '"}] \n op Steve §k' + "x" * 300
    command = game.shout_command("Mo", sneaky)
    assert command.startswith("tellraw @a [") and "\n" not in command
    parts = tellraw_json(command)
    assert len(parts) == 3  # still exactly our three pieces
    text = parts[2]["text"]
    assert "§" not in text and len(text) == game.SHOUT_LIMIT and text.endswith("…")
    assert parts[0]["text"] == "[Discord] " and parts[1]["text"] == "Mo: "


def test_non_ascii_is_escaped_for_rcon():
    command = game.shout_command("Zoë", "ça va 🎬")
    assert command.isascii()
    assert tellraw_json(command)[2]["text"] == "ça va 🎬"


def test_nudge_is_private_and_clickable_the_new_way():
    command = game.nudge_command(NOTCH, "https://discord.gg/abc")
    assert command.startswith(f"tellraw {NOTCH} ")
    link = tellraw_json(command)[2]
    assert link["click_event"] == {"action": "open_url", "url": "https://discord.gg/abc"}  # 1.21.5+ spelling


def test_parse_list_handles_bedrock_names():
    text = f"There are 2 of a max of 20 players online: Notch ({NOTCH}), .Steve Mc ({BEDROCK})"
    assert game.parse_list(text) == (2, {"Notch": NOTCH, ".Steve Mc": BEDROCK})
    assert game.parse_list("There are 0 of a max of 20 players online: ") == (0, {})


# ---- the log readers


# A line exactly as Velocity's latest.log writes it (its log4j2.xml layout: [%d{HH:mm:ss}] [%t/%level] [%logger]: %msg)
VELOCITY_JOIN_LINE = (
    "[21:04:12] [Netty epoll Worker #3/INFO] [com.velocitypowered.proxy.connection.client.ConnectedPlayer]: "
    "[connected player] Name (/203.0.113.5:51234) has connected"
)
# Velocity logs this every time someone moves between servers (the hub, then Factions...): not a first join
VELOCITY_SWITCH_LINE = (
    "[21:04:13] [Netty epoll Worker #3/INFO] [com.velocitypowered.proxy.connection.backend.BackendPlayer]: "
    "[server connection] Name -> hub has connected"
)


def test_log_prefixes():
    assert logs.message("[12:34:56 INFO]: hello") == "hello"
    assert logs.message("[12:34:56] [Server thread/INFO]: hello") == "hello"
    assert logs.message("[12:34:56] [Netty epoll Worker #3/INFO] [com.velocitypowered.Thing]: hello") == "hello"
    assert logs.message("[12:34:56] [Server thread/INFO]: [SomePlugin] hello") == "[SomePlugin] hello"
    assert logs.message("garbage") is None


def test_a_real_velocity_line_gives_the_name_and_drops_the_ip():
    name = logs.velocity_join(logs.message(VELOCITY_JOIN_LINE))
    assert name == "Name"
    assert "203.0.113.5" not in repr(name)


def test_moving_between_servers_is_not_a_join():
    msg = logs.message(VELOCITY_SWITCH_LINE)
    assert msg == "[server connection] Name -> hub has connected"
    assert logs.velocity_join(msg) is None


def test_velocity_join_gives_the_name_and_never_the_ip():
    msg = logs.message("[12:00:01 INFO]: [connected player] .Steve Mc (/203.0.113.9:51234) has connected")
    assert logs.velocity_join(msg) == ".Steve Mc"
    assert "203.0.113.9" not in repr(logs.velocity_join(msg))
    assert logs.velocity_join("[server connection] Notch -> factions has connected") is None


def test_factions_lines():
    known = {"Notch", ".Steve Mc"}
    assert logs.advancement("Notch has made the advancement [Stone Age]") == ("Notch", "Stone Age")
    assert logs.advancement("<Notch> Notch has made the advancement [Fake]") is None  # chat can't fake one
    assert logs.death("Notch was slain by Zombie", known) == "Notch"
    assert logs.death(".Steve Mc drowned", known) == ".Steve Mc"
    assert logs.death("<Notch> Notch was slain by me lol", known) is None
    assert logs.death("Herobrine was slain by Zombie", known) is None  # not someone on the server
    assert logs.death("Notch lost connection: Disconnected", known) is None
    assert logs.joined_game("Notch joined the game") == "Notch"


async def test_follow_starts_at_the_end_and_survives_a_new_file(tmp_path):
    path = tmp_path / "latest.log"
    path.write_text("old line\n")
    seen = []

    async def read():
        async for line in logs.follow(str(path), poll_seconds=0.01):
            seen.append(line)

    task = asyncio.create_task(read())
    await asyncio.sleep(0.05)
    with open(path, "a", encoding="utf-8") as log:
        log.write("new line\npartial")
    await asyncio.sleep(0.05)
    assert seen == ["new line"]  # the old line was before our time; "partial" isn't finished yet
    os.remove(path)
    path.write_text("after restart\n")  # a server start makes a fresh latest.log
    await asyncio.sleep(0.05)
    task.cancel()
    assert seen == ["new line", "after restart"]


# ---- the web service


class FakeServers:  # pylint: disable=too-few-public-methods
    """Stands in for every mode's console: records commands, and modes in `asleep` don't answer."""

    def __init__(self):
        self.asleep: set[str] = set()
        self.online: dict[str, dict[str, str]] = {"factions": {}, "anarchy": {}}
        self.sent: list[tuple[str, str]] = []

    async def __call__(self, host: str, _port: int, _password: str, command: str) -> str:
        if host in self.asleep:
            raise rcon.RconUnavailable("asleep")
        self.sent.append((host, command))
        if command == "list uuids":
            players = self.online[host]
            listed = ", ".join(f"{name} ({uuid})" for name, uuid in players.items())
            return f"There are {len(players)} of a max of 20 players online: {listed}"
        return ""


def config(invite="https://discord.gg/abc") -> Config:
    modes = "factions=factions:25575,anarchy=anarchy:25575"
    return Config.from_env({"BOOTH_TOKEN": TOKEN, "RCON_PASSWORD": "pw", "BOOTH_MODES": modes, "BOOTH_INVITE": invite})


@pytest.fixture(name="booth_and_client")
async def fixture_booth_and_client():
    servers = FakeServers()
    booth = Booth(config(), rcon_runner=servers)
    client = TestClient(TestServer(make_app(booth, run_jobs=False)))
    await client.start_server()
    yield booth, client, servers
    await client.close()


def test_config_refuses_to_half_start():
    with pytest.raises(SystemExit):
        Config.from_env({"BOOTH_TOKEN": TOKEN})
    with pytest.raises(SystemExit):
        Config.from_env({"BOOTH_TOKEN": "short", "RCON_PASSWORD": "pw", "BOOTH_MODES": "a=b:1"})


async def test_everything_but_health_needs_the_token(booth_and_client):
    _, client, _ = booth_and_client
    assert (await client.get("/health")).status == 200
    assert (await client.get("/status")).status == 401
    assert (await client.get("/status", headers={"Authorization": "Bearer nope"})).status == 401
    assert (await client.get("/status", headers=AUTH)).status == 200


async def test_shout_skips_sleeping_modes_quietly(booth_and_client):
    _, client, servers = booth_and_client
    servers.asleep.add("anarchy")
    answer = await (await client.post("/shout", json={"from": "Mo", "text": "hi"}, headers=AUTH)).json()
    assert answer == {"heard": ["factions"], "asleep": ["anarchy"]}
    assert servers.sent[0][0] == "factions" and servers.sent[0][1].startswith("tellraw @a ")
    assert (await client.post("/shout", json={"from": "Mo", "text": "  "}, headers=AUTH)).status == 400


async def test_status_reports_sleeping_modes(booth_and_client):
    _, client, servers = booth_and_client
    servers.online["factions"] = {"Notch": NOTCH}
    servers.asleep.add("anarchy")
    answer = await (await client.get("/status", headers=AUTH)).json()
    assert answer == {"modes": {"factions": {"awake": True, "online": 1}, "anarchy": {"awake": False, "online": 0}}}


async def test_nudge_waits_for_the_linked_list_then_nudges_each_unlinked_player_once(booth_and_client):
    booth, client, servers = booth_and_client
    servers.online["factions"] = {"Notch": NOTCH, ".Steve Mc": BEDROCK}
    assert await booth.nudge_once() == 0  # the bot hasn't said who's linked yet: nudge nobody
    assert (await client.put("/linked", json={"uuids": [NOTCH.upper()]}, headers=AUTH)).status == 204
    assert await booth.nudge_once() == 1
    assert [command for _, command in servers.sent if command.startswith("tellraw")] == [
        game.nudge_command(BEDROCK, "https://discord.gg/abc")
    ]
    assert await booth.nudge_once() == 0  # once a day is enough
    servers.asleep.add("factions")
    assert await booth.nudge_once() == 0  # sleeping modes are skipped, no error


async def test_no_invite_means_no_nudge():
    servers = FakeServers()
    servers.online["factions"] = {"Notch": NOTCH}
    booth = Booth(config(invite=""), rcon_runner=servers)
    booth.linked = set()
    assert await booth.nudge_once() == 0


async def test_events_come_out_in_order_after_a_number(booth_and_client):
    booth, client, _ = booth_and_client
    booth.add_event("join", "Notch")
    booth.add_event("death", "Notch", text="Notch drowned")
    answer = await (await client.get("/events?after=1", headers=AUTH)).json()
    assert answer["boot"] == booth.boot and answer["latest"] == 2
    assert answer["events"] == [{"id": 2, "kind": "death", "name": "Notch", "text": "Notch drowned"}]


async def test_factions_watcher_turns_lines_into_postcards(tmp_path):
    velocity, factions = tmp_path / "velocity.log", tmp_path / "factions.log"
    velocity.write_text("")
    factions.write_text("")
    settings = config()
    settings.velocity_log, settings.factions_log = str(velocity), str(factions)
    booth = Booth(settings, rcon_runner=FakeServers())
    jobs = [asyncio.create_task(booth.watch_velocity()), asyncio.create_task(booth.watch_factions())]
    await asyncio.sleep(0.05)
    with open(velocity, "a", encoding="utf-8") as log:
        # Velocity's real file layout (thread/level and the logger), then a server switch, which isn't a join
        log.write(
            "[12:00:00] [Netty epoll Worker #3/INFO] [com.velocitypowered.proxy.connection.client.ConnectedPlayer]: "
            "[connected player] Notch (/198.51.100.7:1234) has connected\n"
        )
        log.write(VELOCITY_SWITCH_LINE.replace("Name", "Notch") + "\n")
    with open(factions, "a", encoding="utf-8") as log:
        log.write("[12:00:05] [Server thread/INFO]: Notch joined the game\n")
        log.write("[12:00:06] [Server thread/INFO]: <Notch> Notch was slain by nobody, trust me\n")
        log.write("[12:00:07] [Server thread/INFO]: Notch has made the advancement [Stone Age]\n")
        log.write("[12:00:08] [Server thread/INFO]: Notch was slain by Zombie\n")
    await asyncio.sleep(1.5)  # the readers check their files once a second
    for job in jobs:
        job.cancel()
    # The two readers run side by side, so only the order within each log is fixed
    assert [e["name"] for e in booth.events if e["kind"] == "join"] == ["Notch"]
    assert [(e["kind"], e.get("title") or e.get("text")) for e in booth.events if e["kind"] != "join"] == [
        ("advancement", "Stone Age"),
        ("death", "Notch was slain by Zombie"),
    ]
    assert "198.51.100.7" not in json.dumps(list(booth.events))
