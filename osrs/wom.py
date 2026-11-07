"""A tiny Wise Old Man client. It answers one question: who's in the clan?

The clan's group on Wise Old Man (https://wiseoldman.net/groups/7117) syncs with the in-game clan by itself,
so its member list is the clan's member list. Reading it is public: no key or verification code needed.
"""

import logging
import time
from typing import Optional

import aiohttp

from osrs.accounts import rsn_key

WOM_API = "https://api.wiseoldman.net/v2"
CLAN_GROUP_ID = 7117  # "Ugandans" on Wise Old Man
# WOM asks every app to identify itself, so they can get in touch instead of banning an unknown caller
USER_AGENT = "VideoJoker Discord bot (github.com/morgan-vanv/VideoJoker)"
CACHE_SECONDS = 10 * 60  # the member list barely changes; asking at most every 10 minutes is polite

_cache: Optional[tuple[float, frozenset[str]]] = None  # (when we fetched it, the members' rsn_keys)


def member_keys_from_group(group: dict) -> frozenset[str]:
    """Pulls the members' names out of WOM's "group details" answer.

    It looks like {"name": "Ugandans", "memberships": [{"role": ..., "player": {"username": "swannobi", ...}}, ...]}.
    A frozenset is a set that can't be changed afterwards, which is what you want for a shared cache.
    """
    return frozenset(rsn_key(membership["player"]["username"]) for membership in group.get("memberships", []))


async def clan_member_keys(session: aiohttp.ClientSession) -> Optional[frozenset[str]]:
    """The rsn_keys of everyone in the clan, or None if Wise Old Man can't be reached right now.

    Callers treat None as "don't know": the bot then just asks people instead of guessing.
    """
    global _cache  # pylint: disable=global-statement  # one small module-level cache is simpler than a class here
    if _cache and time.monotonic() - _cache[0] < CACHE_SECONDS:
        return _cache[1]
    try:
        async with session.get(
            f"{WOM_API}/groups/{CLAN_GROUP_ID}",
            headers={"User-Agent": USER_AGENT},
            timeout=aiohttp.ClientTimeout(total=10),
        ) as response:
            response.raise_for_status()  # turns 429 (too many requests), 500 etc. into an exception
            members = member_keys_from_group(await response.json())
    except (aiohttp.ClientError, TimeoutError, KeyError, ValueError) as error:
        logging.warning("Couldn't read the clan from Wise Old Man: %s", error)
        return None
    _cache = (time.monotonic(), members)
    return members
