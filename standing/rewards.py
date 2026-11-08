"""When a slash command earns XP. Plain rules, so the test doesn't need a clock or Discord."""

from typing import Optional


def command_xp_due(last_rewarded: Optional[float], now: float, cooldown: float) -> bool:
    """True if a command run at `now` should earn XP: the person's first command, or `cooldown` seconds since the
    last one that earned some. Times come from time.monotonic(), a clock that only ever goes forward (unlike the
    wall clock, which can jump when the server's time is corrected)."""
    return last_rewarded is None or now - last_rewarded >= cooldown
