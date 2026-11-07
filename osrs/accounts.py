"""OSRS name rules: is this a valid name, and when are two names "the same"? Pure Python, no Discord."""

import re
from typing import Optional

# Jagex's rules: 1-12 characters, made of letters, digits, spaces, hyphens and underscores
_VALID_RSN = re.compile(r"[A-Za-z0-9 _-]{1,12}")


def clean_rsn(text: str) -> Optional[str]:
    """Returns the name tidied up (outer spaces trimmed), or None if it can't be an OSRS name."""
    # The game itself (and pages copied from it) often uses a "non-breaking space" ( ) between words.
    # It looks like a space but isn't one, so swap it for a real space before checking.
    rsn = text.replace(" ", " ").strip()
    if _VALID_RSN.fullmatch(rsn):
        return rsn
    return None


def rsn_key(rsn: str) -> str:
    """The name in the form we compare with: lowercase, with '-' and '_' as spaces.

    OSRS treats "Iron_Morph", "iron-morph" and "IRON MORPH" as the same player, and so does Wise Old Man.
    Storing this "key" next to the name means we can spot duplicates no matter how someone types it.
    """
    return re.sub(r"[-_\s]", " ", rsn).strip().lower()
