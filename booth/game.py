"""What the booth says in game, and how it reads what the game says back. Pure Python, all tested.

In-game messages are sent with `tellraw`, which takes a "text component": a little JSON description of coloured,
clickable text. Since Minecraft 1.21.5 the click part is spelled `click_event` with a `url` (it used to be
`clickEvent` with a `value`); our servers run 26.x, so we use the new spelling.

We build the JSON with json.dumps, never by gluing strings together: whatever someone types in Discord ends up
safely inside a JSON string and can't break out into a second command. ensure_ascii (json.dumps' default) turns
anything that isn't plain ASCII into \\u escapes, which both RCON and Minecraft read without trouble.
"""

import json
import re
from typing import NamedTuple

SHOUT_LIMIT = 200  # characters a shout can have in game
NAME_LIMIT = 32
_CONTROL = re.compile(r"[\x00-\x1f\x7f§]")  # control characters, and § (Minecraft's old colour-code sign)


class Mode(NamedTuple):
    """A Minecraft server the booth can talk to: its name and where its RCON listens."""

    name: str
    host: str
    port: int


def parse_modes(text: str) -> list[Mode]:
    """BOOTH_MODES, e.g. "factions=factions:25575,anarchy=anarchy:25575" → [Mode(...), Mode(...)]."""
    modes = []
    for part in filter(None, (piece.strip() for piece in text.split(","))):
        name, _, address = part.partition("=")
        host, _, port = address.rpartition(":")
        if not name or not host or not port.isdigit():
            raise ValueError(f"BOOTH_MODES entry {part!r} should look like name=host:port")
        modes.append(Mode(name.strip(), host.strip(), int(port)))
    if not modes:
        raise ValueError("BOOTH_MODES lists no modes")
    return modes


def clean(text: str, limit: int) -> str:
    """Removes control characters and § codes, squeezes spaces, and cuts to the limit."""
    text = " ".join(_CONTROL.sub(" ", text).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def shout_command(sender: str, text: str) -> str:
    """`tellraw @a` for a /mc shout: [Discord] Name: message."""
    component = [
        {"text": "[Discord] ", "color": "blue"},
        {"text": f"{clean(sender, NAME_LIMIT)}: ", "color": "aqua"},
        {"text": clean(text, SHOUT_LIMIT), "color": "white"},
    ]
    return "tellraw @a " + json.dumps(component)


def nudge_command(uuid: str, invite: str) -> str:
    """A private `tellraw` to one player who hasn't linked an account: join the Discord, then /mc register."""
    component = [
        {"text": "[VJ] ", "color": "gold"},
        {"text": "Not in our Discord yet? "},
        {"text": invite, "color": "aqua", "underlined": True, "click_event": {"action": "open_url", "url": invite}},
        {"text": " - then type /mc register there to link your account."},
    ]
    return f"tellraw {uuid} " + json.dumps(component)


# `list uuids` answers "There are 2 of a max of 20 players online: Steve (069a...-...), .Bedrock Guy (0000...)".
_LISTED = re.compile(r"(?:: |, )(.+?) \(([0-9a-fA-F-]{36})\)")
_COUNT = re.compile(r"There are (\d+)")


def parse_list(text: str) -> tuple[int, dict[str, str]]:
    """(how many are online, {name: uuid}) from the console's answer to `list uuids`."""
    players = {name: uuid.lower() for name, uuid in _LISTED.findall(text)}
    count = _COUNT.search(text)
    return (int(count.group(1)) if count else len(players)), players
