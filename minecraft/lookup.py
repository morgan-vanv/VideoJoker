"""Looks up Minecraft accounts by name, so a typo is caught and we store the account's UUID.

Two public services, no keys needed:
- Java: Mojang's own API answers "which account has this name?" with its UUID and the name as it's spelled.
- Bedrock: GeyserMC's Global API (the people who make Geyser, which lets Bedrock players onto our Java server)
  turns an Xbox gamertag into its XUID, the number Floodgate builds the player's in-game UUID from.

Both are asked only when someone links an account, so we stay far below their limits.
"""

import logging
from urllib.parse import quote
from typing import NamedTuple, Optional

import aiohttp

from minecraft.accounts import floodgate_uuid, java_uuid

MOJANG_PROFILE = "https://api.mojang.com/users/profiles/minecraft/{name}"
GEYSER_XUID = "https://api.geysermc.org/v2/xbox/xuid/{gamertag}"
GEYSER_GAMERTAG = "https://api.geysermc.org/v2/xbox/gamertag/{xuid}"
USER_AGENT = "VideoJoker Discord bot (github.com/morgan-vanv/VideoJoker)"
TIMEOUT = aiohttp.ClientTimeout(total=10)


class Profile(NamedTuple):
    uuid: str
    name: str  # as the account spells it


class LookupUnavailable(Exception):
    """The service didn't answer properly (down, or rate-limited). Not the same as "no such account"."""


async def _get_json(session: aiohttp.ClientSession, url: str) -> Optional[dict]:
    """GET a JSON answer. None means "no such account"; LookupUnavailable means "couldn't ask"."""
    try:
        async with session.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT) as response:
            if response.status in (204, 404):  # Mojang's ways of saying "nobody has that name"
                return None
            response.raise_for_status()
            return await response.json()
    except (aiohttp.ClientError, TimeoutError, ValueError) as error:
        # The URL holds the name being looked up, so only the error's kind goes in the log
        logging.warning("Minecraft account lookup failed: %s", type(error).__name__)
        raise LookupUnavailable from error


async def find_java(session: aiohttp.ClientSession, name: str) -> Optional[Profile]:
    data = await _get_json(session, MOJANG_PROFILE.format(name=quote(name)))
    if not data or "id" not in data:
        return None
    return Profile(java_uuid(data["id"]), data.get("name", name))


async def find_bedrock(session: aiohttp.ClientSession, gamertag: str) -> Optional[Profile]:
    data = await _get_json(session, GEYSER_XUID.format(gamertag=quote(gamertag)))
    if not data or "xuid" not in data:  # an empty answer means there's no Xbox account with that gamertag
        return None
    xuid = int(data["xuid"])
    # Ask for the gamertag back too, so we store it spelled the way Xbox spells it. If that fails, keep theirs.
    try:
        spelled = await _get_json(session, GEYSER_GAMERTAG.format(xuid=xuid))
    except LookupUnavailable:
        spelled = None
    name = spelled.get("gamertag", gamertag) if spelled else gamertag
    return Profile(floodgate_uuid(xuid), name)


async def find(session: aiohttp.ClientSession, name: str, edition: str) -> Optional[Profile]:
    """The account with this name on this edition, or None if there isn't one. Raises LookupUnavailable."""
    if edition == "bedrock":
        return await find_bedrock(session, name)
    return await find_java(session, name)
