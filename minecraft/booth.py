"""The bot's side of the booth: a small client for the booth's web service (booth/app.py lists its menu).

The booth runs next to the Minecraft servers, on another machine. The bot reaches it over Morgan's private network
(the tailnet) at BOOTH_URL, showing BOOTH_TOKEN with every request. Both settings are optional: without them the
booth features (/mc shout, postcards, per-mode counts) switch off and everything else keeps working.
"""

from typing import NamedTuple, Optional

import aiohttp

TIMEOUT = aiohttp.ClientTimeout(total=10)


class ModeStatus(NamedTuple):
    awake: bool
    online: int


class ShoutResult(NamedTuple):
    heard: list[str]  # modes that showed the shout
    asleep: list[str]  # modes that were asleep (skipped)


class Postcards(NamedTuple):
    boot: str  # changes when the booth restarts (its event numbers start over)
    latest: int  # the newest event's number
    events: list[dict]  # {"id", "kind": "join"|"death"|"advancement", "name", "text"?, "title"?}


class BoothUnavailable(Exception):
    """The booth didn't answer properly. Not the same as "every mode is asleep" (that's an empty `heard`)."""


class BoothClient:
    def __init__(self, session: aiohttp.ClientSession, url: str, token: str):
        self.session = session
        self.url = url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {token}"}

    async def _call(self, method: str, path: str, **kwargs) -> Optional[dict]:
        try:
            async with self.session.request(
                method, self.url + path, headers=self.headers, timeout=TIMEOUT, **kwargs
            ) as response:
                response.raise_for_status()
                return await response.json() if response.status != 204 else None
        except (aiohttp.ClientError, TimeoutError, ValueError) as error:
            raise BoothUnavailable(type(error).__name__) from error

    async def status(self) -> dict[str, ModeStatus]:
        data = await self._call("GET", "/status")
        return {name: ModeStatus(bool(mode["awake"]), int(mode["online"])) for name, mode in data["modes"].items()}

    async def shout(self, sender: str, text: str) -> ShoutResult:
        data = await self._call("POST", "/shout", json={"from": sender, "text": text})
        return ShoutResult(list(data["heard"]), list(data["asleep"]))

    async def put_linked(self, uuids: list[str]) -> None:
        await self._call("PUT", "/linked", json={"uuids": uuids})

    async def postcards(self, after: int) -> Postcards:
        data = await self._call("GET", "/events", params={"after": str(after)})
        return Postcards(str(data["boot"]), int(data["latest"]), list(data["events"]))
