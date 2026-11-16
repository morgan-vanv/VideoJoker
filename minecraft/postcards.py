"""What the VJ posts for each postcard from the booth. Pure Python, tested.

Three kinds, decided by the infra side and Morgan: a player's first time on the network (from any mode), and
deaths and advancements on Factions only. Anarchy stays raw: nothing from it ever reaches here.
"""

from typing import Optional

import discord

from minecraft import lines

FLOODGATE_PREFIX = "."  # Bedrock players show up in game as ".Gamertag"


def account_name(in_game: str) -> tuple[str, str]:
    """(edition, name as we store it) for a name as the server shows it: ".Steve Mc" is the Bedrock gamertag
    "Steve Mc", anything else a Java name."""
    if in_game.startswith(FLOODGATE_PREFIX):
        return "bedrock", in_game[len(FLOODGATE_PREFIX) :]
    return "java", in_game


def text_for(event: dict, owner_ids: list[int]) -> Optional[str]:
    """The postcard for one booth event, naming the linked Discord member(s) (the post never pings), or None for
    an event we don't make postcards of."""
    name = discord.utils.escape_markdown(str(event.get("name", "")))
    if not name:
        return None
    kind = event.get("kind")
    if kind == "join":
        text = lines.POSTCARD_JOIN.format(name=name)
    elif kind == "death" and event.get("text"):
        text = lines.POSTCARD_DEATH.format(text=discord.utils.escape_markdown(str(event["text"])))
    elif kind == "advancement" and event.get("title"):
        text = lines.POSTCARD_ADVANCEMENT.format(name=name, title=discord.utils.escape_markdown(str(event["title"])))
    else:
        return None
    if owner_ids:
        text += lines.POSTCARD_OWNER.format(members=", ".join(f"<@{owner}>" for owner in owner_ids))
    return text
