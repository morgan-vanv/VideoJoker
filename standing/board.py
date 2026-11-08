"""Leaderboard maths with no Discord in sight: who's in which place, ties included.

Places work like a sports table ("competition ranking"): two people level on points share a place, and the next
place is skipped. Scores 50, 40, 40, 10 are places 1, 2, 2, 4.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Placing:
    """One row of a leaderboard."""

    place: int  # 1 = top
    user_id: int
    score: int  # XP or USh, whichever board this is


def placings(scores: dict[int, int]) -> list[Placing]:
    """Everyone with more than 0, best first. Ties share a place; among equals, the older Discord account (smaller
    id) is listed first, just so the order doesn't jump around between runs."""
    ranked = sorted(((user_id, score) for user_id, score in scores.items() if score > 0), key=lambda r: (-r[1], r[0]))
    rows = []
    for index, (user_id, score) in enumerate(ranked):
        if rows and rows[-1].score == score:
            place = rows[-1].place  # level with the one above: same place
        else:
            place = index + 1  # otherwise your place is how many are ahead of you, plus one
        rows.append(Placing(place, user_id, score))
    return rows


def place_of(rows: list[Placing], user_id: int) -> Optional[Placing]:
    """Someone's row, or None if they aren't on the board (nothing yet, or not in this server)."""
    return next((row for row in rows if row.user_id == user_id), None)


def top_with_you(rows: list[Placing], viewer_id: int, top: int = 10) -> tuple[list[Placing], Optional[Placing]]:
    """The top `top` rows, plus the viewer's own row if they didn't make the cut (None if they did, or if they
    aren't on the board at all)."""
    shown = rows[:top]
    if any(row.user_id == viewer_id for row in shown):
        return shown, None
    return shown, place_of(rows, viewer_id)
