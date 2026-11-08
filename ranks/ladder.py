"""The rank ladder's rules, with no Discord in sight, so tests can check them directly.

Everything here works on plain numbers: XP totals and role IDs. The cog (cogs/ranks.py) turns a Discord
member into "which role IDs do they hold?", asks these functions what to do, and then does it.

The three promises the ladder keeps:
1. You get the highest rank your XP has earned (LOWLY SERFS on your first message).
2. Never a demotion: if you already hold a rank equal to or above what you've earned (say, from Pancake),
   the ladder leaves you alone completely.
3. One rank at a time (ranks are mutually exclusive): when you're promoted, the lower ladder roles come off
   in the same step. Lower ones only, never the one you hold at the top.

XP is a lifetime total (1 per message, 5 per command; see core/database.py): it never resets on a promotion,
so the thresholds below are totals to reach, not amounts to earn per rank.
"""

from dataclasses import dataclass
from typing import Iterable, Optional

# Our server's ladder. Tier 1 is the bottom rung. Thresholds are lifetime XP totals.
TIER_NAMES = {1: "LOWLY SERFS", 2: "SWORN SWORDS", 3: "LORDS"}
DEFAULT_MIN_XP = {1: 1, 2: 250, 3: 1000}


@dataclass(frozen=True)
class Tier:
    """One rung of the ladder. frozen=True makes it read-only, so a tier can't be changed by accident."""

    number: int  # 1 = lowest
    role_id: int
    min_xp: int


@dataclass(frozen=True)
class RoleChange:
    """What to do to one member: add one role, take some lower ones off."""

    tier: Tier  # the rank they end up with
    add: Optional[int]  # role ID to add, or None if they already have it
    remove: tuple[int, ...]  # lower ladder role IDs to take off


def problems_with(tiers: list[Tier]) -> list[str]:
    """Checks a ladder before saving it. Returns what's wrong, in plain words (an empty list means it's fine)."""
    problems = []
    role_ids = [tier.role_id for tier in tiers]
    if len(set(role_ids)) != len(role_ids):
        problems.append("Each rank needs its own role.")
    ordered = sorted(tiers, key=lambda tier: tier.number)
    if ordered and ordered[0].min_xp < 1:
        problems.append("The first rank needs at least 1 XP.")
    for lower, higher in zip(ordered, ordered[1:]):
        if higher.min_xp <= lower.min_xp:
            problems.append(
                f"{TIER_NAMES.get(higher.number, f'Tier {higher.number}')} must need more XP than "
                f"{TIER_NAMES.get(lower.number, f'Tier {lower.number}')} ({higher.min_xp} ≤ {lower.min_xp})."
            )
    return problems


def earned_tier(tiers: Iterable[Tier], xp: int) -> Optional[Tier]:
    """The highest tier this much XP has earned, or None if not even the first one."""
    earned = [tier for tier in tiers if xp >= tier.min_xp]
    return max(earned, key=lambda tier: tier.number, default=None)


def held_tier(tiers: Iterable[Tier], role_ids: set[int]) -> Optional[Tier]:
    """The highest ladder tier whose role the member already has, or None."""
    held = [tier for tier in tiers if tier.role_id in role_ids]
    return max(held, key=lambda tier: tier.number, default=None)


def _lower_roles_held(tiers: Iterable[Tier], role_ids: set[int], top: Tier) -> tuple[int, ...]:
    """Ladder roles below `top` that the member is still wearing."""
    return tuple(tier.role_id for tier in tiers if tier.number < top.number and tier.role_id in role_ids)


def plan_promotion(tiers: list[Tier], xp: int, role_ids: set[int]) -> Optional[RoleChange]:
    """What to do after a member's XP went up. None means "leave them alone" (the usual answer)."""
    earned = earned_tier(tiers, xp)
    if earned is None:
        return None
    held = held_tier(tiers, role_ids)
    if held is not None and held.number >= earned.number:
        return None  # promise 2: already at or above what they've earned, so hands off
    return RoleChange(tier=earned, add=earned.role_id, remove=_lower_roles_held(tiers, role_ids, earned))


def plan_tidy(tiers: list[Tier], role_ids: set[int]) -> Optional[RoleChange]:
    """For /ladder tidy: if a member wears several ladder roles (Pancake stacked them), keep only the highest.
    Never adds a role and never touches the top one, so nobody's rank goes down."""
    held = held_tier(tiers, role_ids)
    if held is None:
        return None
    lower = _lower_roles_held(tiers, role_ids, held)
    if not lower:
        return None
    return RoleChange(tier=held, add=None, remove=lower)


def xp_shortfall(tiers: list[Tier], role_ids: set[int], xp: int) -> int:
    """For /ladder tidy: how much XP someone is missing for the rank they already wear (0 if none).
    Pancake's ranks came from Pancake's XP, so a LORD can have almost no VideoJoker XP. Topping them up to their
    rank's minimum makes the numbers match the roles, and their next promotion comes at the right time."""
    held = held_tier(tiers, role_ids)
    if held is None:
        return 0
    return max(0, held.min_xp - xp)
