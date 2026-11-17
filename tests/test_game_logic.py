"""Tests for pure game logic: no Discord, no database."""

import random

from cogs.fun import curse_of_ra
from core.constants import (
    CURSE_OF_RA_FIRST_GLYPH,
    CURSE_OF_RA_LAST_GLYPH,
    CURSE_OF_RA_LENGTH,
    EIGHT_BALL_RESPONSES,
    RPS_CHOICES,
    RPS_WINNING_CONDITIONS,
)
from games import dice
from games.three_card_monte.engine import deal_winning_card


def test_monte_deals_one_of_the_three_cards():
    # The card is random, so deal many times and check every result is valid
    dealt = {deal_winning_card() for _ in range(200)}
    assert dealt <= {"A", "B", "C"}
    assert len(dealt) == 3  # 200 deals all missing one card would be astronomically unlikely


def test_rps_each_choice_beats_exactly_one_other():
    assert set(RPS_WINNING_CONDITIONS) == set(RPS_CHOICES)
    assert set(RPS_WINNING_CONDITIONS.values()) == set(RPS_CHOICES)
    for choice, beats in RPS_WINNING_CONDITIONS.items():
        assert choice != beats
        assert RPS_WINNING_CONDITIONS[beats] != choice  # no two choices beat each other


def test_the_8_ball_has_something_to_say():
    assert EIGHT_BALL_RESPONSES and all(answer.strip() for answer in EIGHT_BALL_RESPONSES)


def test_the_curse_of_ra_pings_its_target_and_is_made_of_real_hieroglyphs():
    curse = curse_of_ra("<@123>")
    assert curse.startswith("**shut up, <@123>** ")
    assert curse.endswith(" **(CURSE OF RA)**")

    glyphs = curse.removeprefix("**shut up, <@123>** ").removesuffix(" **(CURSE OF RA)**")
    assert len(glyphs) == CURSE_OF_RA_LENGTH
    assert all(CURSE_OF_RA_FIRST_GLYPH <= ord(glyph) <= CURSE_OF_RA_LAST_GLYPH for glyph in glyphs)
    assert len(curse) <= 2000  # one Discord message
    assert curse != curse_of_ra("<@123>")  # a fresh curse every time


def test_roll_is_one_d6_by_default_and_checks_its_limits():
    assert dice.problem(6, 1) is None
    assert dice.problem(dice.MAX_SIDES, dice.MAX_DICE) is None
    assert dice.problem(6, 0) == "You did not roll any dice!"
    assert dice.problem(6, dice.MAX_DICE + 1) == f"You can only roll up to {dice.MAX_DICE} dice!"
    assert dice.problem(0, 1) == "A die must have at least 1 side!"
    assert dice.problem(200, 1) == "Sorry, we don't have any 200-sided dice :("


def test_roll_stays_on_the_dice():
    rolls = dice.roll(20, 10, random.Random(3))
    assert len(rolls) == 10 and all(1 <= number <= 20 for number in rolls)


def test_roll_reads_well():
    assert dice.describe("mo", 6, [4]) == "mo rolled a **4** (d6)"
    assert dice.describe("mo", 20, [7, 20, 11]) == "mo rolled 3d20: **7, 20, 11** (total **38**)"
