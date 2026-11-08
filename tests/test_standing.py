"""Tests for standing/: leaderboard places, the command XP cooldown, and the copy built from the XP numbers."""

from core.database import COMMAND_XP_COOLDOWN_SECONDS, USH_PER_MESSAGE, XP_PER_COMMAND, XP_PER_MESSAGE, UshMove
from standing import lines
from standing.board import Placing, place_of, placings, top_with_you
from standing.rewards import command_xp_due

ALICE, BOB, CAROL, DAVE = 1, 2, 3, 4  # fake Discord user ids


# ---- Places, ties included


def test_ties_share_a_place_and_the_next_place_is_skipped():
    rows = placings({ALICE: 50, BOB: 40, CAROL: 40, DAVE: 10})
    assert [(row.place, row.user_id) for row in rows] == [(1, ALICE), (2, BOB), (2, CAROL), (4, DAVE)]


def test_nobody_with_zero_is_on_the_board():
    assert placings({ALICE: 0, BOB: 3}) == [Placing(1, BOB, 3)]
    assert not placings({})


def test_place_of_someone_not_on_the_board_is_none():
    rows = placings({ALICE: 5})
    assert place_of(rows, ALICE) == Placing(1, ALICE, 5)
    assert place_of(rows, BOB) is None


def test_top_ten_with_your_own_row_when_you_are_further_down():
    scores = {user_id: 100 - user_id for user_id in range(1, 31)}  # user 1 has the most, user 30 the least
    shown, you = top_with_you(placings(scores), viewer_id=23)
    assert len(shown) == 10 and shown[0].user_id == 1
    assert you == Placing(23, 23, 77)


def test_no_extra_row_when_you_are_in_the_top_ten_or_not_on_the_board():
    rows = placings({ALICE: 5, BOB: 3})
    assert top_with_you(rows, viewer_id=BOB)[1] is None
    assert top_with_you(rows, viewer_id=CAROL)[1] is None


# ---- Command XP cooldown


def test_first_command_earns_xp():
    assert command_xp_due(None, now=5.0, cooldown=60)


def test_a_command_within_the_cooldown_earns_nothing():
    assert not command_xp_due(100.0, now=159.9, cooldown=60)


def test_a_command_after_the_cooldown_earns_again():
    assert command_xp_due(100.0, now=160.0, cooldown=60)


# ---- Copy built from the real numbers


def test_earning_line_uses_the_real_numbers():
    assert lines.EARNING == (
        f"Every message: {XP_PER_MESSAGE} XP + {USH_PER_MESSAGE} USh. "
        f"Every command: {XP_PER_COMMAND} XP ({lines.cooldown_words(COMMAND_XP_COOLDOWN_SECONDS)})."
    )


def test_cooldown_words():
    assert lines.cooldown_words(60) == "once a minute"
    assert lines.cooldown_words(120) == "once every 2 minutes"
    assert lines.cooldown_words(45) == "once every 45 seconds"


def test_payment_lines_from_both_sides():
    move = UshMove(ALICE, BOB, 50, "pay", "for the *popcorn*", 1_700_000_000)
    assert lines.move_line(move, ALICE) == '➡️ Sent **50 USh** to <@2> · "for the \\*popcorn\\*" · <t:1700000000:R>'
    assert lines.move_line(move, BOB).startswith("⬅️ Got **50 USh** from <@1>")


def test_the_bank_has_no_mention():
    payout = UshMove(None, ALICE, 10, "gamble", None, 1_700_000_000)
    assert lines.move_line(payout, ALICE) == "⬅️ Got **10 USh** from the bank · <t:1700000000:R>"


def test_board_rows_have_medals_then_numbers():
    assert lines.board_row(Placing(1, ALICE, 4210), "XP", is_you=False) == "🥇 <@1> · 4,210 XP"
    assert lines.board_row(Placing(4, BOB, 12), "USh", is_you=True) == "**`#4` <@2> · 12 USh** ← you"
