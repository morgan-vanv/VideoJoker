"""Tests for the rank ladder's rules (ranks/ladder.py) and its storage (core/database.py).

The ladder on our server: LOWLY SERFS at 1 XP, SWORN SWORDS at 250, LORDS at 1000. Role IDs here are fake.
"""

import aiosqlite

from core.database import Database, RankUpNote
from ranks.ladder import (
    DEFAULT_MIN_XP,
    Tier,
    earned_tier,
    plan_promotion,
    plan_tidy,
    problems_with,
    progress_bar,
    rank_progress,
    xp_shortfall,
)
from ranks.notes import and_list, permission_words, rank_up_note, unlocked_permissions

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


def test_tidy_tops_up_xp_to_the_rank_they_wear():
    assert xp_shortfall(LADDER, {LORDS}, 3) == 997  # a Pancake lord with 3 VJ XP gets topped up to 1000
    assert xp_shortfall(LADDER, {SERFS, SWORDS}, 0) == 250  # the highest rank they wear counts
    assert xp_shortfall(LADDER, {SWORDS}, 400) == 0  # already enough
    assert xp_shortfall(LADDER, {STAFF}, 0) == 0  # no rank, nothing to back up


# ---- Checking a ladder before it's saved


def test_good_ladder_has_no_problems():
    assert not problems_with(LADDER)


def test_thresholds_must_go_up():
    assert problems_with([Tier(1, SERFS, 1), Tier(2, SWORDS, 1000), Tier(3, LORDS, 1000)])
    assert problems_with([Tier(1, SERFS, 1), Tier(2, SWORDS, 500), Tier(3, LORDS, 250)])


def test_each_rank_needs_its_own_role():
    assert problems_with([Tier(1, SERFS, 1), Tier(2, SERFS, 250), Tier(3, LORDS, 1000)])


# ---- Where am I on the ladder? (/rank and /ladder show)


def test_progress_counts_towards_the_next_rank():
    progress = rank_progress(LADDER, 612, {SWORDS})
    assert progress.tier.role_id == SWORDS
    assert progress.next_tier.role_id == LORDS
    assert progress.to_go == 388  # XP never resets, so it's 1,000 minus everything so far


def test_newcomer_with_no_xp_is_heading_for_serfs():
    progress = rank_progress(LADDER, 0, set())
    assert progress.tier is None
    assert progress.next_tier.role_id == SERFS
    assert progress.to_go == 1


def test_the_rank_you_wear_wins_over_your_xp():
    # A Pancake-era LORD with hardly any VideoJoker XP is still a LORD, and at the top
    progress = rank_progress(LADDER, 5, {LORDS, STAFF})
    assert progress.tier.role_id == LORDS
    assert progress.next_tier is None and progress.to_go == 0


def test_without_a_ladder_role_your_xp_decides():
    progress = rank_progress(LADDER, 300, {STAFF})
    assert progress.tier.role_id == SWORDS
    assert progress.to_go == 700


def test_earned_but_not_yet_worn_means_nothing_to_go():
    # Wears SWORDS but already has LORDS' XP (say the ladder was off): the next XP promotes them
    assert rank_progress(LADDER, 1500, {SWORDS}).to_go == 0


def test_progress_bar():
    assert progress_bar(612, 1000) == "▰▰▰▰▰▰▱▱▱▱"
    assert progress_bar(0, 1000) == "▱" * 10
    assert progress_bar(999, 1000) == "▰" * 9 + "▱"  # rounded down: only full once you're there
    assert progress_bar(1000, 1000) == "▰" * 10
    assert progress_bar(5000, 1000) == "▰" * 10  # never more than full


# ---- Storage


async def test_messages_and_commands_add_up_to_one_xp_total(db):
    assert await db.add_server_xp(1) == 1  # a message: 1 XP
    assert await db.add_server_xp(1) == 2
    assert await db.add_bot_xp(1) == 7  # a command: 5 XP
    totals = await db.get_xp_totals(1)
    assert (totals.messages, totals.commands, totals.bonus, totals.total) == (2, 1, 0, 7)
    assert await db.get_xp(1) == (2, 1)  # the raw counts still mean what they always meant


async def test_xp_is_lifetime_and_never_resets(db):
    for _ in range(1000):
        await db.add_server_xp(1)
    assert await db.add_server_xp(1) == 1001  # past LORDS and still counting up


async def test_top_up_raises_xp_to_a_minimum_and_never_lowers_it(db):
    await db.add_server_xp(1)
    assert await db.top_up_xp(1, 250) == 250
    assert (await db.get_xp_totals(1)).bonus == 249
    assert await db.top_up_xp(1, 100) == 250  # already above: nothing taken away
    assert await db.add_server_xp(1) == 251  # and it keeps growing from there
    assert await db.top_up_xp(2, 1000) == 1000  # someone the bot has never seen gets a row


async def test_all_total_xp(db):
    await db.add_server_xp(1)
    await db.add_bot_xp(2)
    assert await db.get_all_total_xp() == {1: 1, 2: 5}


async def test_an_existing_database_gets_the_bonus_column(tmp_path):
    # A database made by the code on main (no bonus_xp column), with someone's XP already in it
    path = tmp_path / "old.db"
    async with aiosqlite.connect(path) as conn:
        await conn.execute(
            "CREATE TABLE xp (user_id INTEGER PRIMARY KEY, server_xp INTEGER DEFAULT 0, bot_xp INTEGER DEFAULT 0)"
        )
        await conn.execute("INSERT INTO xp VALUES (1, 10, 2)")
        await conn.commit()
    database = Database(db_path=path)
    await database.setup()
    try:
        assert (await database.get_xp_totals(1)).total == 20  # 10 messages + 2 commands x 5
    finally:
        await database.close()


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


# ---- The rank-up note (ranks/notes.py)

# What the roles allow on our server today. @everyone has the basics; each ladder role carries its whole tier's perks.
EVERYONE_PERMS = {"view_channel", "send_messages", "read_message_history", "connect", "speak"}
SERFS_PERMS = {"attach_files", "add_reactions", "external_emojis", "change_nickname"}
SWORDS_PERMS = SERFS_PERMS | {"create_expressions", "create_instant_invite", "send_tts_messages"}
LORDS_PERMS = SWORDS_PERMS | {"move_members"}


def test_serfs_unlock_their_perks():
    assert unlocked_permissions(SERFS_PERMS | {"send_messages"}, EVERYONE_PERMS, []) == SERFS_PERMS


def test_swords_unlock_only_what_serfs_did_not_have():
    unlocked = unlocked_permissions(SWORDS_PERMS, EVERYONE_PERMS, [SERFS_PERMS])
    assert unlocked == {"create_expressions", "create_instant_invite", "send_tts_messages"}


def test_lords_unlock_moving_people():
    assert unlocked_permissions(LORDS_PERMS, EVERYONE_PERMS, [SERFS_PERMS, SWORDS_PERMS]) == {"move_members"}


def test_a_rank_with_nothing_new_unlocks_nothing():
    assert unlocked_permissions(SERFS_PERMS, EVERYONE_PERMS | SERFS_PERMS, []) == set()


def test_permission_words_are_friendly_ordered_and_have_a_fallback():
    words = permission_words({"send_tts_messages", "create_instant_invite", "create_expressions", "send_polls"})
    assert words == ["add emojis and stickers", "create invites", "send text-to-speech messages", "send polls"]


def test_both_names_for_external_emoji_show_once():
    assert permission_words({"external_emojis", "use_external_emojis"}) == ["use emoji from other servers"]


def test_and_list():
    assert and_list([]) == ""
    assert and_list(["a"]) == "a"
    assert and_list(["a", "b"]) == "a and b"
    assert and_list(["a", "b", "c"]) == "a, b and c"


def test_note_with_unlocks_and_xp_to_go():
    progress = rank_progress(LADDER, 250, {SWORDS})
    unlocked = {"create_expressions", "create_instant_invite", "send_tts_messages"}
    assert rank_up_note(progress, unlocked) == (
        "🎖️ You've climbed to **SWORN SWORDS**! 750 XP to **LORDS**.\n"
        "New with this rank: add emojis and stickers, create invites and send text-to-speech messages."
    )


def test_note_at_the_top_of_the_ladder():
    note = rank_up_note(rank_progress(LADDER, 1000, {LORDS}), {"move_members"})
    assert note == (
        "🎖️ You've climbed to **LORDS**! That's the top of the ladder, comrade.\n"
        "New with this rank: move people between voice channels."
    )


def test_note_without_unlocks_has_no_unlocks_line():
    note = rank_up_note(rank_progress(LADDER, 1, {SERFS}), set())
    assert note == "🎖️ You've climbed to **LOWLY SERFS**! 249 XP to **SWORN SWORDS**."


def test_note_counts_xp_to_go_from_now():
    # A note that waited: they've kept chatting since they climbed, so it's 612 XP now, not 250
    assert "388 XP to **LORDS**" in rank_up_note(rank_progress(LADDER, 612, {SWORDS}), set())


# ---- Rank-up notes in the database


async def test_no_note_waiting_by_default(db):
    assert await db.take_rank_up_note(GUILD, 1) is None


async def test_a_note_is_taken_only_once(db):
    await db.save_rank_up_note(GUILD, 1, 2)
    note = await db.take_rank_up_note(GUILD, 1)
    assert note.tier == 2 and note.created_at > 0
    assert await db.take_rank_up_note(GUILD, 1) is None


async def test_notes_are_per_person_per_server(db):
    await db.save_rank_up_note(GUILD, 1, 1)
    await db.save_rank_up_note(GUILD + 1, 1, 3)
    await db.save_rank_up_note(GUILD, 2, 2)
    assert (await db.take_rank_up_note(GUILD + 1, 1)).tier == 3
    assert (await db.take_rank_up_note(GUILD, 1)).tier == 1
    assert (await db.take_rank_up_note(GUILD, 2)).tier == 2


async def test_climbing_twice_keeps_only_the_latest_note(db):
    await db.save_rank_up_note(GUILD, 1, 1)
    await db.save_rank_up_note(GUILD, 1, 2)
    assert (await db.take_rank_up_note(GUILD, 1)).tier == 2
    assert await db.take_rank_up_note(GUILD, 1) is None


async def test_a_note_that_failed_to_send_can_be_put_back(db):
    await db.save_rank_up_note(GUILD, 1, 2)
    note = await db.take_rank_up_note(GUILD, 1)
    await db.put_back_rank_up_note(GUILD, 1, note)
    assert await db.take_rank_up_note(GUILD, 1) == note


async def test_putting_back_never_overwrites_a_newer_note(db):
    old = RankUpNote(tier=1, created_at=100)
    await db.save_rank_up_note(GUILD, 1, 2)  # they climbed again while the old note was out for delivery
    await db.put_back_rank_up_note(GUILD, 1, old)
    assert (await db.take_rank_up_note(GUILD, 1)).tier == 2


async def test_notes_survive_a_restart(db, tmp_path):
    # Deploys restart the bot often: a fresh start on the same file (the db fixture's) still has the note
    await db.save_rank_up_note(GUILD, 1, 3)
    database = Database(db_path=tmp_path / "test.db")
    await database.setup()
    try:
        assert (await database.take_rank_up_note(GUILD, 1)).tier == 3
    finally:
        await database.close()


async def test_an_existing_database_gets_the_notes_table(tmp_path):
    # A database made before rank-up notes existed: setup() adds the table, and the ladder is untouched
    path = tmp_path / "old.db"
    async with aiosqlite.connect(path) as conn:
        await conn.execute(
            "CREATE TABLE rank_tiers (guild_id INTEGER NOT NULL, tier INTEGER NOT NULL, role_id INTEGER NOT NULL,"
            " min_xp INTEGER NOT NULL CHECK(min_xp >= 1), PRIMARY KEY (guild_id, tier))"
        )
        await conn.execute("INSERT INTO rank_tiers VALUES (?, 1, ?, 1)", (GUILD, SERFS))
        await conn.commit()
    database = Database(db_path=path)
    await database.setup()
    try:
        assert len(await database.get_all_rank_tiers()) == 1
        await database.save_rank_up_note(GUILD, 1, 1)
        assert (await database.take_rank_up_note(GUILD, 1)).tier == 1
    finally:
        await database.close()
