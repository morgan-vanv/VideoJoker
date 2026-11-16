"""Small decisions the Minecraft cog makes, kept apart from Discord so they're easy to test."""

from typing import Collection, Optional

from minecraft import lines
from minecraft.ping import ServerStatus


def should_welcome(
    role_id: int,
    before_roles: Collection[int],
    after_roles: Collection[int],
    before_pending: bool,
    after_pending: bool,
) -> bool:
    """Does this member update mean "welcome them now"?

    Yes when they have the role *and* are through the server's join gate now, but didn't have both a moment ago.
    "Pending" is Discord's word for someone who joined but hasn't finished the rules/application step yet: the
    onboarding question can hand out the role before that, so we wait until they're really in.
    """
    in_now = role_id in after_roles and not after_pending
    in_before = role_id in before_roles and not before_pending
    return in_now and not in_before


def status_line(status: Optional[ServerStatus]) -> str:
    """The marquee's first line: up (and how full) or down. None means the ping failed."""
    if status is None:
        return lines.STATUS_DOWN
    if status.online == 0:
        return lines.STATUS_UP_EMPTY
    return lines.STATUS_UP.format(online=status.online, max=status.max_players)
