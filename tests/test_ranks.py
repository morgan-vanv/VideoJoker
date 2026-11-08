"""Tests for the rank ladder's rules (ranks/ladder.py) and its storage (core/database.py).

The ladder on our server: LOWLY SERFS at 1 XP, SWORN SWORDS at 250, LORDS at 1000. Role IDs here are fake.
"""

from ranks.ladder import DEFAULT_MIN_XP, Tier, earned_tier, plan_promotion, plan_tidy, problems_with

SERFS, SWORDS, LORDS = 101, 102, 103  # fake role ids
STAFF = 999  # some role that isn't on the ladder (e.g. los manos)
GUILD = 5000
LADDER = [Tier(1, SERFS, 1), Tier(2, SWORDS, 250), Tier(3, LORDS, 1000)]


# ---- Which rank does this much XP earn?


def test_no_xp_earns_nothing():
    assert earned_tier(LADDER, 0) is None


def test_first_message_earns_serfs():
    assert earned_tier(LADDER, 1).role_id == SERFS


def test_thresholds_are_inclusive():
    assert earned_tier(LADDER, 249).role_id == SERFS
    assert earned_tier(LADDER, 250).role_id == SWORDS
    assert earned_tier(LADDER, 999).role_id == SWORDS
    assert earned_tier(LADDER, 1000).role_id == LORDS
    assert earned_tier(LADDER, 50_000).role_id == LORDS  # no rank above the top


def test_defaults_match_the_agreed_ladder():
    assert DEFAULT_MIN_XP == {1: 1, 2: 250, 3: 1000}


# ---- Promotions


def test_newcomer_gets_serfs_on_first_message():
    change = plan_promotion(LADDER, 1, set())
    assert change.add == SERFS and change.remove == ()


def test_promotion_swaps_out_the_lower_rank():
    change = plan_promotion(LADDER, 250, {SERFS, STAFF})
    assert change.add == SWORDS
    assert change.remove == (SERFS,)  # mutually exclusive: SERFS comes off in the same step


def test_promotion_takes_off_every_lower_rank_and_nothing_else():
    change = plan_promotion(LADDER, 1000, {SERFS, SWORDS, STAFF})
    assert change.add == LORDS
    assert set(change.remove) == {SERFS, SWORDS}  # STAFF isn't a ladder role, so it's never touched


def test_already_holding_the_earned_rank_means_no_change():
    assert plan_promotion(LADDER, 300, {SWORDS}) is None


# ---- Never demote, never downgrade (Pancake's 156 / 26 / 22 keep what they have)


def test_pancake_lord_with_no_vj_xp_is_left_alone():
    # Prod XP started counting on 2026-11-07, so Pancake's lords start near 0 XP. Hands off.
    assert plan_promotion(LADDER, 1, {LORDS}) is None


def test_pancake_sword_is_left_alone_until_they_earn_lords():
    assert plan_promotion(LADDER, 1, {SWORDS}) is None
    assert plan_promotion(LADDER, 999, {SWORDS}) is None
    assert plan_promotion(LADDER, 1000, {SWORDS}).add == LORDS


def test_stacked_pancake_member_is_not_touched_below_their_rank():
    # Holding SWORDS + SERFS and earning only SERFS: the promise is "don't touch", so SERFS stays too
    assert plan_promotion(LADDER, 1, {SWORDS, SERFS}) is None


def test_a_promotion_never_removes_the_new_rank_or_a_higher_one():
    for xp in (1, 250, 1000, 5000):
        for held in (set(), {SERFS}, {SWORDS}, {LORDS}, {SERFS, SWORDS}, {SERFS, SWORDS, LORDS}):
            change = plan_promotion(LADDER, xp, held)
            if change is None:
                continue
            removed_tiers = [tier for tier in LADDER if tier.role_id in change.remove]
            assert all(tier.number < change.tier.number for tier in removed_tiers)
            assert change.add not in change.remove


# ---- /ladder tidy


def test_tidy_keeps_only_the_highest_rank():
    change = plan_tidy(LADDER, {SERFS, SWORDS, LORDS, STAFF})
    assert change.add is None  # tidy never hands out a role
    assert set(change.remove) == {SERFS, SWORDS}


def test_tidy_leaves_single_rank_and_unranked_members_alone():
    assert plan_tidy(LADDER, {SWORDS}) is None
    assert plan_tidy(LADDER, {STAFF}) is None
    assert plan_tidy(LADDER, set()) is None


# ---- Checking a ladder before it's saved


def test_good_ladder_has_no_problems():
    assert not problems_with(LADDER)


def test_thresholds_must_go_up():
    assert problems_with([Tier(1, SERFS, 1), Tier(2, SWORDS, 1000), Tier(3, LORDS, 1000)])
    assert problems_with([Tier(1, SERFS, 1), Tier(2, SWORDS, 500), Tier(3, LORDS, 250)])


def test_each_rank_needs_its_own_role():
    assert problems_with([Tier(1, SERFS, 1), Tier(2, SERFS, 250), Tier(3, LORDS, 1000)])


# ---- Storage


async def test_add_server_xp_returns_the_new_total(db):
    assert await db.add_server_xp(1) == 1
    assert await db.add_server_xp(1) == 2
    assert await db.add_server_xp(1, 5) == 7
    assert await db.get_xp(1) == (7, 0)


async def test_no_ladder_by_default(db):
    assert await db.get_all_rank_tiers() == []


async def test_ladder_is_saved_replaced_and_cleared_per_server(db):
    await db.set_rank_tiers(GUILD, [(1, SERFS, 1), (2, SWORDS, 250), (3, LORDS, 1000)])
    await db.set_rank_tiers(GUILD + 1, [(1, 7, 1)])
    await db.set_rank_tiers(GUILD, [(1, SERFS, 1), (2, SWORDS, 300), (3, LORDS, 1200)])  # replaces, not adds

    rows = [row for row in await db.get_all_rank_tiers() if row.guild_id == GUILD]
    assert [(row.tier, row.role_id, row.min_xp) for row in rows] == [(1, SERFS, 1), (2, SWORDS, 300), (3, LORDS, 1200)]

    await db.clear_rank_tiers(GUILD)
    assert [row.guild_id for row in await db.get_all_rank_tiers()] == [GUILD + 1]  # the other server is untouched
