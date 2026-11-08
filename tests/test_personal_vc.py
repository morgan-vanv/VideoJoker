"""Tests for personal voice channels: the rules (personal_vc/rules.py), the VJ's lines (personal_vc/lines.py) and
the storage (core/database.py). IDs here are fake."""

import pytest

from core.database import PersonalVcConfig
from personal_vc import lines
from personal_vc.rules import (
    CREATE_COOLDOWN,
    LET_IN,
    MAX_NAME_LENGTH,
    Mode,
    channel_name,
    cooldown_left,
    let_in_ids,
    mode_from_db,
    mode_layer,
    should_delete,
)

GUILD = 5000  # the server, and so also its @everyone role (they share an id)
OWNER, BOT, GUEST, VISITOR = 1, 2, 3, 4  # members
STAFF, MEMBERS_ROLE = 900, 901  # roles: moderators, and a role the category allows in


# ---- Names, cooldown, deleting


def test_channel_is_named_after_the_owner():
    assert channel_name("Morgan") == "Morgan's voice channel"


def test_long_names_are_cut_to_discords_limit():
    name = channel_name("x" * 300)
    assert len(name) == MAX_NAME_LENGTH
    assert name.endswith("'s voice channel")  # the name gets cut, never the "'s voice channel"


def test_no_cooldown_the_first_time():
    assert cooldown_left(None, now=500.0) == 0.0


def test_cooldown_counts_down_and_stops_at_zero():
    assert cooldown_left(100.0, now=100.0) == CREATE_COOLDOWN
    assert cooldown_left(100.0, now=104.0) == CREATE_COOLDOWN - 4
    assert cooldown_left(100.0, now=100.0 + CREATE_COOLDOWN) == 0.0
    assert cooldown_left(100.0, now=999.0) == 0.0  # never negative


def test_channel_goes_when_the_last_person_leaves():
    assert should_delete(0)
    assert not should_delete(1)


# ---- Modes


def test_unknown_or_missing_mode_means_open():
    assert mode_from_db(None) is Mode.OPEN
    assert mode_from_db("disco") is Mode.OPEN  # say, saved by a newer version after a rollback
    assert mode_from_db("hidden") is Mode.HIDDEN


def test_mode_is_stored_as_a_plain_string():
    assert Mode.LOCKED == "locked"


def test_open_channels_are_left_exactly_like_the_category():
    let_in = let_in_ids(Mode.OPEN, [OWNER, BOT, STAFF], guests=[GUEST], present=[VISITOR])
    assert let_in == set()
    assert mode_layer(Mode.OPEN, GUILD, [GUILD, MEMBERS_ROLE], let_in) == {}


def test_locked_and_hidden_let_in_owner_bot_staff_guests_and_whoevers_inside():
    for mode in (Mode.LOCKED, Mode.HIDDEN):
        let_in = let_in_ids(mode, [OWNER, BOT, STAFF], guests=[GUEST], present=[VISITOR, OWNER])
        assert let_in == {OWNER, BOT, STAFF, GUEST, VISITOR}


def test_locked_everyone_can_see_but_not_join():
    layer = mode_layer(Mode.LOCKED, GUILD, [GUILD], {OWNER, BOT})
    assert layer[GUILD] == {"connect": False}  # View Channel untouched: still visible
    assert layer[OWNER] == LET_IN and layer[BOT] == LET_IN


def test_hidden_everyone_can_neither_see_nor_join():
    layer = mode_layer(Mode.HIDDEN, GUILD, [GUILD], {OWNER, BOT})
    assert layer[GUILD] == {"view_channel": False, "connect": False}
    assert layer[OWNER] == LET_IN


def test_roles_the_category_lets_in_go_neutral_so_the_lock_holds():
    # The category allows MEMBERS_ROLE to connect. A role's allow beats the @everyone deny, so it must go neutral.
    locked = mode_layer(Mode.LOCKED, GUILD, [GUILD, MEMBERS_ROLE], {OWNER})
    assert locked[MEMBERS_ROLE] == {"connect": None}  # seeing it is still up to the category
    hidden = mode_layer(Mode.HIDDEN, GUILD, [GUILD, MEMBERS_ROLE], {OWNER})
    assert hidden[MEMBERS_ROLE] == {"view_channel": None, "connect": None}


def test_staff_in_the_category_still_get_in():
    # The staff role also has a category overwrite: being let in wins over going neutral
    layer = mode_layer(Mode.HIDDEN, GUILD, [GUILD, STAFF], {OWNER, STAFF})
    assert layer[STAFF] == LET_IN


def test_layer_entries_are_separate_copies():
    layer = mode_layer(Mode.HIDDEN, GUILD, [GUILD], {OWNER, BOT})
    layer[OWNER]["connect"] = False
    assert layer[BOT] == LET_IN and LET_IN == {"view_channel": True, "connect": True}


# ---- What the VJ says


def test_panel_wording_is_morgans():
    assert lines.PANEL == "It's your space, so you set the rules -- have fun being mysterious."


def test_welcome_back_mentions_mode_and_guests():
    assert lines.welcome_back("Morgan", Mode.LOCKED, 3) == (
        "Back again, Morgan. Your channel stays 🔒 locked, 3 guests on the list."
    )
    assert lines.welcome_back("Morgan", Mode.HIDDEN, 1).endswith("👻 hidden, 1 guest on the list.")
    assert lines.welcome_back("Morgan", Mode.OPEN, 2).endswith("🔓 open, 2 guests on the list.")
    assert lines.welcome_back("Morgan", Mode.LOCKED, 0).endswith("nobody on the list.")


def test_no_welcome_back_when_nothing_was_remembered():
    assert lines.welcome_back("Morgan", Mode.OPEN, 0) is None


def test_every_mode_has_its_lines():
    for mode in Mode:
        assert mode in lines.MODE_LABELS and mode in lines.MODE_SET


# ---- Storage


def config(**changes) -> PersonalVcConfig:
    return PersonalVcConfig(GUILD, 10, None)._replace(**changes)


async def test_off_by_default(db):
    assert await db.get_personal_vc_configs() == []


async def test_config_is_saved_replaced_and_cleared(db):
    await db.set_personal_vc_config(config())
    await db.set_personal_vc_config(config(hub_channel_id=12, staff_role_id=STAFF))  # replaces, not adds
    await db.set_personal_vc_config(config(guild_id=GUILD + 1))
    saved = {row.guild_id: row for row in await db.get_personal_vc_configs()}
    assert saved[GUILD] == PersonalVcConfig(GUILD, 12, STAFF)
    assert len(saved) == 2

    await db.clear_personal_vc_config(GUILD)
    assert [row.guild_id for row in await db.get_personal_vc_configs()] == [GUILD + 1]


async def test_channels_know_their_owner(db):
    await db.add_personal_channel(100, GUILD, OWNER)
    assert await db.get_personal_channel_owner(100) == OWNER
    assert await db.get_owned_personal_channel(GUILD, OWNER) == 100
    assert await db.get_owned_personal_channel(GUILD + 1, OWNER) is None  # per server
    assert await db.get_personal_channel_owner(101) is None  # not a personal channel

    await db.remove_personal_channel(100)
    assert await db.get_owned_personal_channel(GUILD, OWNER) is None
    assert await db.get_all_personal_channels() == []


async def test_one_channel_per_person_a_new_one_replaces_a_stale_row(db):
    await db.add_personal_channel(100, GUILD, OWNER)
    await db.add_personal_channel(200, GUILD, OWNER)  # channel 100 vanished without us noticing
    assert await db.get_owned_personal_channel(GUILD, OWNER) == 200
    assert [row.channel_id for row in await db.get_all_personal_channels()] == [200]


async def test_mode_is_remembered_per_server(db):
    assert await db.get_personal_vc_mode(GUILD, OWNER) is None
    await db.set_personal_vc_mode(GUILD, OWNER, "locked")
    await db.set_personal_vc_mode(GUILD, OWNER, "hidden")
    assert await db.get_personal_vc_mode(GUILD, OWNER) == "hidden"
    assert await db.get_personal_vc_mode(GUILD + 1, OWNER) is None


async def test_unknown_mode_is_refused(db):
    with pytest.raises(ValueError):
        await db.set_personal_vc_mode(GUILD, OWNER, "disco")


async def test_guest_list_adds_without_doubles_and_removes(db):
    await db.add_personal_vc_guests(GUILD, OWNER, [GUEST, VISITOR])
    await db.add_personal_vc_guests(GUILD, OWNER, [GUEST])  # already on it: not doubled
    assert await db.get_personal_vc_guests(GUILD, OWNER) == [GUEST, VISITOR]  # in the order they were let in
    assert await db.get_personal_vc_guests(GUILD, VISITOR) == []  # everyone has their own list

    await db.remove_personal_vc_guests(GUILD, OWNER, [GUEST, 12345])  # someone not on it: no error
    assert await db.get_personal_vc_guests(GUILD, OWNER) == [VISITOR]


def test_other_peoples_buttons_say_whose_channel_it_is():
    line = lines.NOT_YOURS.format(owner="<@1>", hub="<#2>")
    assert line.startswith("🎞️ Not your voice channel") and "<@1>" in line and "<#2>" in line
