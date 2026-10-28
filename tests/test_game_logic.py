"""Tests for pure game logic: no Discord, no database."""
from core.constants import EIGHT_BALL_RESPONSES, ROASTS, RPS_CHOICES, RPS_WINNING_CONDITIONS
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
