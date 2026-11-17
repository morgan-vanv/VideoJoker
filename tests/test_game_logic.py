"""Tests for pure game logic: no Discord, no database."""

from cogs.fun import curse_of_ra
from core.constants import (
    CURSE_OF_RA_FIRST_GLYPH,
    CURSE_OF_RA_LAST_GLYPH,
    CURSE_OF_RA_LENGTH,
    EIGHT_BALL_RESPONSES,
    ROASTS,
    RPS_CHOICES,
    RPS_WINNING_CONDITIONS,
)
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


def test_the_8_ball_and_the_roasts_have_something_to_say():
    assert EIGHT_BALL_RESPONSES and all(answer.strip() for answer in EIGHT_BALL_RESPONSES)
    assert ROASTS and all(roast.strip() for roast in ROASTS)


def test_the_curse_of_ra_pings_its_target_and_is_made_of_real_hieroglyphs():
    curse = curse_of_ra("<@123>")
    assert curse.startswith("**shut up, <@123>** ")
    assert curse.endswith(" **(CURSE OF RA)**")

    glyphs = curse.removeprefix("**shut up, <@123>** ").removesuffix(" **(CURSE OF RA)**")
    assert len(glyphs) == CURSE_OF_RA_LENGTH
    assert all(CURSE_OF_RA_FIRST_GLYPH <= ord(glyph) <= CURSE_OF_RA_LAST_GLYPH for glyph in glyphs)
    assert len(curse) <= 2000  # one Discord message
    assert curse != curse_of_ra("<@123>")  # a fresh curse every time
