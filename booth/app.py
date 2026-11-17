"""The booth's web service: a short, fixed menu the bot can order from, plus three jobs that run on their own.

The menu (every request needs the header "Authorization: Bearer <BOOTH_TOKEN>", except /health):
  GET  /health          "ok", for monitoring
  GET  /status          players online in each mode, and which modes are asleep
  POST /shout           {"from": "Name", "text": "..."}: a [Discord] message to every awake mode
  PUT  /linked          {"uuids": [...]}: who has linked an account (so the nudge leaves them alone)
  GET  /events?after=N  postcards: first joins (whole network), deaths and advancements (Factions)

The jobs: watch Velocity's log for joins, watch Factions' log for deaths and advancements, and every 30 seconds
nudge players who haven't linked an account yet ("join our Discord"), at most once a day each.

There's deliberately no "run this command" on the menu: if the token ever leaked, the worst anyone could do is
shout or ask who's online, never op themselves or stop a server.

Player names never go into this service's log, and IP addresses never leave the log reader (booth/logs.py).
"""

import asyncio
import hmac
import logging
import os
import secrets
import time
from collections import deque
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional

from aiohttp import web

from booth import game, logs, rcon

NUDGE_EVERY_SECONDS = 30
FACTIONS_MEMORY_SECONDS = 6 * 60 * 60  # how long a name counts as "on Factions" after we last saw it
EVENTS_KEPT = 500  # the bot asks every 15 seconds, so this is hours of slack

RconRunner = Callable[[str, int, str, str], Awaitable[str]]


@dataclass
class Config:  # pylint: disable=too-many-instance-attributes  # one per setting
    token: str
    rcon_password: str
    modes: list[game.Mode]
    invite: Optional[str] = None  # no invite = no nudge
    factions_mode: str = "factions"
    velocity_log: str = "/logs/velocity/latest.log"
    factions_log: str = "/logs/factions/latest.log"
    nudge_hours: float = 24
    port: int = 8765

    @classmethod
    def from_env(cls, env: dict[str, str]) -> "Config":
        """Reads the settings. Missing required ones stop the booth with a clear message: a booth that half
        works is harder to notice than one that won't start."""
        missing = [name for name in ("BOOTH_TOKEN", "RCON_PASSWORD", "BOOTH_MODES") if not env.get(name)]
        if missing:
            raise SystemExit(f"The booth needs {', '.join(missing)} (see booth/README.md).")
        if len(env["BOOTH_TOKEN"]) < 32:
            raise SystemExit("BOOTH_TOKEN should be at least 32 characters (openssl rand -hex 32).")
        return cls(
            token=env["BOOTH_TOKEN"],
            rcon_password=env["RCON_PASSWORD"],
            modes=game.parse_modes(env["BOOTH_MODES"]),
            invite=env.get("BOOTH_INVITE") or None,
            factions_mode=env.get("BOOTH_FACTIONS_MODE", "factions"),
            velocity_log=env.get("BOOTH_VELOCITY_LOG", cls.velocity_log),
            factions_log=env.get("BOOTH_FACTIONS_LOG", cls.factions_log),
            nudge_hours=float(env.get("BOOTH_NUDGE_HOURS", "24")),
            port=int(env.get("BOOTH_PORT", "8765")),
        )


class Booth:  # pylint: disable=too-many-instance-attributes
    """Everything the booth remembers. All of it lives in memory: a restart forgets who was nudged (they may get
    one more nudge) and the postcard queue (the bot notices the new `boot` and starts over)."""

    def __init__(self, config: Config, rcon_runner: RconRunner = rcon.run):
        self.config = config
        self.rcon_runner = rcon_runner
        self.boot = secrets.token_hex(8)  # changes every start, so the bot knows the event numbers restarted
        self.events: deque[dict] = deque(maxlen=EVENTS_KEPT)
        self.next_event_id = 1
        self.linked: Optional[set[str]] = None  # None until the bot first tells us: nudge nobody before that
        self.nudged: dict[str, float] = {}  # uuid → when we last nudged them
        self.on_factions: dict[str, float] = {}  # name → when we last saw them on Factions (for death messages)
        self.warned_refused: set[str] = set()

    # ---- talking to the servers

    async def console(self, mode: game.Mode, command: str) -> Optional[str]:
        """Runs a command in one mode's console. None means the mode is asleep (or its password is wrong, which
        is logged once): callers skip it quietly."""
        try:
            return await self.rcon_runner(mode.host, mode.port, self.config.rcon_password, command)
        except rcon.RconUnavailable:
            return None
        except rcon.RconRefused:
            if mode.name not in self.warned_refused:
                self.warned_refused.add(mode.name)
                logging.error("RCON refused the password for %s: check RCON_PASSWORD", mode.name)
            return None

    async def everywhere(self, command: str) -> tuple[list[str], list[str]]:
        """Runs a command in every mode at once. Returns (modes that heard it, modes that are asleep)."""
        answers = await asyncio.gather(*(self.console(mode, command) for mode in self.config.modes))
        heard = [mode.name for mode, answer in zip(self.config.modes, answers) if answer is not None]
        asleep = [mode.name for mode, answer in zip(self.config.modes, answers) if answer is None]
        return heard, asleep

    async def who_is_on(self) -> dict[str, Optional[tuple[int, dict[str, str]]]]:
        """For each mode: (how many online, {name: uuid}), or None if it's asleep."""
        answers = await asyncio.gather(*(self.console(mode, "list uuids") for mode in self.config.modes))
        return {
            mode.name: (game.parse_list(answer) if answer is not None else None)
            for mode, answer in zip(self.config.modes, answers)
        }

    # ---- postcards

    def add_event(self, kind: str, name: str, **details: str) -> None:
        self.events.append({"id": self.next_event_id, "kind": kind, "name": name, **details})
        self.next_event_id += 1

    def remember_on_factions(self, name: str) -> None:
        now = time.monotonic()
        self.on_factions[name] = now
        for old in [n for n, seen in self.on_factions.items() if now - seen > FACTIONS_MEMORY_SECONDS]:
            del self.on_factions[old]

    async def watch_velocity(self) -> None:
        async for line in logs.follow(self.config.velocity_log):
            msg = logs.message(line)
            name = logs.velocity_join(msg) if msg else None
            if name:
                self.add_event("join", name)

    async def watch_factions(self) -> None:
        async for line in logs.follow(self.config.factions_log):
            msg = logs.message(line)
            if not msg:
                continue
            if name := logs.joined_game(msg):
                self.remember_on_factions(name)
            elif found := logs.advancement(msg):
                self.add_event("advancement", found[0], title=found[1])
            elif name := logs.death(msg, set(self.on_factions)):
                self.add_event("death", name, text=msg)

    # ---- the nudge

    async def nudge_once(self) -> int:
        """Looks at who's on every awake mode; nudges anyone unlinked who wasn't nudged lately. Returns how many."""
        on = await self.who_is_on()
        for name in (on.get(self.config.factions_mode) or (0, {}))[1]:
            self.remember_on_factions(name)
        if not self.config.invite or self.linked is None:
            return 0
        now = time.time()
        sent = 0
        for mode in self.config.modes:
            listed = on.get(mode.name)
            if listed is None:
                continue  # asleep: nobody to nudge
            for uuid in listed[1].values():
                if uuid in self.linked or now - self.nudged.get(uuid, 0) < self.config.nudge_hours * 3600:
                    continue
                if await self.console(mode, game.nudge_command(uuid, self.config.invite)) is not None:
                    self.nudged[uuid] = now
                    sent += 1
        return sent

    # ---- jobs that run on their own, restarted if anything goes wrong

    async def forever(self, job: Callable[[], Awaitable[None]], name: str) -> None:
        while True:
            try:
                await job()
            except Exception:  # pylint: disable=broad-exception-caught  # cancelling isn't an Exception: not caught
                logging.exception("The booth's %s job failed; starting it again in 10 seconds.", name)
                await asyncio.sleep(10)

    async def nudge_loop(self) -> None:
        while True:
            sent = await self.nudge_once()
            if sent:
                logging.info("Nudged %d player(s) toward the Discord.", sent)
            await asyncio.sleep(NUDGE_EVERY_SECONDS)


# ---- the web side


def make_app(booth: Booth, run_jobs: bool = True) -> web.Application:
    """The booth's web app. Tests pass run_jobs=False and drive the jobs themselves."""

    @web.middleware
    async def check_token(request: web.Request, handler):
        if request.path != "/health":
            expected = f"Bearer {booth.config.token}".encode()
            given = request.headers.get("Authorization", "").encode()
            # compare_digest takes the same time whether the first or the last character is wrong, so the token
            # can't be guessed one character at a time by timing the answers
            if not hmac.compare_digest(given, expected):
                return web.json_response({"error": "unauthorized"}, status=401)
        return await handler(request)

    async def health(_request: web.Request) -> web.Response:
        return web.Response(text="ok")

    async def status(_request: web.Request) -> web.Response:
        on = await booth.who_is_on()
        modes = {
            name: {"awake": listed is not None, "online": listed[0] if listed else 0} for name, listed in on.items()
        }
        return web.json_response({"modes": modes})

    async def shout(request: web.Request) -> web.Response:
        try:
            body = await request.json()
            sender, text = str(body["from"]), str(body["text"])
        except ValueError, KeyError, TypeError:
            return web.json_response({"error": "send {from, text}"}, status=400)
        if not game.clean(text, game.SHOUT_LIMIT) or not game.clean(sender, game.NAME_LIMIT):
            return web.json_response({"error": "empty"}, status=400)
        heard, asleep = await booth.everywhere(game.shout_command(sender, text))
        logging.info("Shout heard in %s (asleep: %s).", heard or "nowhere", asleep or "none")
        return web.json_response({"heard": heard, "asleep": asleep})

    async def linked(request: web.Request) -> web.Response:
        try:
            uuids = (await request.json())["uuids"]
            if not isinstance(uuids, list) or len(uuids) > 100_000:
                raise TypeError
            booth.linked = {str(uuid).lower() for uuid in uuids}
        except ValueError, KeyError, TypeError:
            return web.json_response({"error": "send {uuids: [...]}"}, status=400)
        return web.Response(status=204)

    async def events(request: web.Request) -> web.Response:
        try:
            after = int(request.query.get("after", "0"))
        except ValueError:
            return web.json_response({"error": "after must be a number"}, status=400)
        newer = [event for event in booth.events if event["id"] > after]
        return web.json_response({"boot": booth.boot, "latest": booth.next_event_id - 1, "events": newer})

    app = web.Application(middlewares=[check_token], client_max_size=64 * 1024)
    app.router.add_get("/health", health)
    app.router.add_get("/status", status)
    app.router.add_post("/shout", shout)
    app.router.add_put("/linked", linked)
    app.router.add_get("/events", events)

    if run_jobs:

        async def start_jobs(app: web.Application) -> None:
            app["jobs"] = [
                asyncio.create_task(booth.forever(booth.watch_velocity, "Velocity log")),
                asyncio.create_task(booth.forever(booth.watch_factions, "Factions log")),
                asyncio.create_task(booth.forever(booth.nudge_loop, "nudge")),
            ]

        async def stop_jobs(app: web.Application) -> None:
            for job in app["jobs"]:
                job.cancel()

        app.on_startup.append(start_jobs)
        app.on_cleanup.append(stop_jobs)
    return app


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    config = Config.from_env(dict(os.environ))
    booth = Booth(config)
    logging.info(
        "The booth is open on port %d for %s (nudge %s).",
        config.port,
        ", ".join(mode.name for mode in config.modes),
        "on" if config.invite else "off: no BOOTH_INVITE",
    )
    web.run_app(make_app(booth), port=config.port, print=None, access_log=None)
