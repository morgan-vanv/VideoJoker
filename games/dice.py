"""/roll: one command for every die. A remux of Frankie's /droll (any number of dice of one number of sides) and
Morgan's /diceroll (one die of any number of sides), merged on 2026-11-16 with Morgan's OK while Frankie is away.
The limits, the "too many dice" lines and the "we don't have any N-sided dice :(" joke are Frankie's.

No Discord in here, so tests/test_game_logic.py checks it all.
"""

import random

MAX_DICE = 10  # Frankie's limit
MAX_SIDES = 100  # Frankie's was 20; 100 lets people roll a d100 (percentile dice)


def problem(sides: int, dice: int) -> str | None:
    """What's wrong with this roll, in words for the person who asked, or None if it's fine."""
    if dice < 1:
        return "You did not roll any dice!"
    if dice > MAX_DICE:
        return f"You can only roll up to {MAX_DICE} dice!"
    if sides < 1:
        return "A die must have at least 1 side!"
    if sides > MAX_SIDES:
        return f"Sorry, we don't have any {sides}-sided dice :("
    return None


def roll(sides: int, dice: int, rng: random.Random | None = None) -> list[int]:
    """Rolls `dice` dice with `sides` sides each. Tests pass a seeded rng to get the same rolls every time."""
    rng = rng or random.Random()
    return [rng.randint(1, sides) for _ in range(dice)]


def describe(name: str, sides: int, rolls: list[int]) -> str:
    """'mo' money rolled a **4** (d6)' for one die, 'mo' money rolled 3d20: **7, 20, 11** (total **38**)' for more."""
    if len(rolls) == 1:
        return f"{name} rolled a **{rolls[0]}** (d{sides})"
    each = ", ".join(str(number) for number in rolls)
    return f"{name} rolled {len(rolls)}d{sides}: **{each}** (total **{sum(rolls)}**)"
