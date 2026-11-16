"""Minecraft name rules and UUIDs. Pure Python, no Discord and no internet, so it's all tested.

Two editions, two kinds of name:
- Java: 1-16 letters, digits or underscores (Mojang's rule; new names need at least 3, a few old ones are shorter).
- Bedrock: the Xbox gamertag, up to 16 letters, digits and spaces (new gamertags can end in a number suffix).
  In game, Geyser's Floodgate shows Bedrock players with a "." in front ("Steve Mc" plays as ".Steve Mc"),
  so we drop a leading "." if someone types it.
"""

import re
import uuid
from typing import Optional

_JAVA_NAME = re.compile(r"[A-Za-z0-9_]{1,16}")
_GAMERTAG = re.compile(r"[A-Za-z0-9 ]{1,16}")


def clean_name(text: str, edition: str) -> Optional[str]:
    """The name tidied up (outer spaces trimmed, a Floodgate "." dropped), or None if it can't be a name."""
    name = text.replace(" ", " ").strip()  # a "non-breaking space" from copy-paste becomes a real one
    if edition == "bedrock":
        name = name.removeprefix(".").strip()
        return name if _GAMERTAG.fullmatch(name) else None
    return name if _JAVA_NAME.fullmatch(name) else None


def java_uuid(mojang_id: str) -> str:
    """Mojang's API gives the UUID as 32 hex digits with no dashes; Minecraft shows it with dashes."""
    return str(uuid.UUID(hex=mojang_id))


def floodgate_uuid(xuid: int) -> str:
    """The UUID a Bedrock player has on the server. Floodgate makes it from the Xbox user ID (XUID): zeros in the
    first half, the XUID in the second, e.g. XUID 2535432196048835 → 00000000-0000-0000-0009-01f64f65c7c3."""
    return str(uuid.UUID(int=xuid))
