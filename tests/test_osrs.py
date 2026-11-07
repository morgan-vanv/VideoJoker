"""Tests for the OSRS features: name rules, Wise Old Man parsing, the flexing kit, the Dink settings file,
and the osrs_accounts / osrs_flexers database methods. No Discord or network needed."""

import json
import types
import re
from pathlib import Path

import pytest

from osrs import flexing, lines
from osrs.accounts import clean_rsn, rsn_key
from osrs.wom import member_keys_from_group

ALICE, BOB = 1, 2  # fake Discord user ids
DINK_SETTINGS = Path(__file__).resolve().parent.parent / "osrs" / "dink-settings.json"


# ---- name rules


@pytest.mark.parametrize("typed, cleaned", [("Swannobi", "Swannobi"), ("  Iron Morph ", "Iron Morph"), ("a", "a")])
def test_valid_names_are_cleaned(typed, cleaned):
    assert clean_rsn(typed) == cleaned


@pytest.mark.parametrize("typed", ["", "   ", "ThirteenChars", "bad!name", "emoji🙂"])
def test_invalid_names_are_rejected(typed):
    assert clean_rsn(typed) is None


def test_non_breaking_space_counts_as_a_space():
    # Copied from the game, a name like "Iron Morph" often has   between the words
    assert clean_rsn("Iron Morph") == "Iron Morph"


def test_same_player_however_its_typed():
    assert rsn_key("Iron_Morph") == rsn_key("iron-morph") == rsn_key("IRON MORPH") == "iron morph"


# ---- Wise Old Man


def test_clan_members_from_a_wom_group():
    group = {
        "name": "Ugandans",
        "memberships": [
            {"role": "member", "player": {"username": "swannobi", "displayName": "Swannobi"}},
            {"role": "member", "player": {"username": "iron morph", "displayName": "Iron_Morph"}},
        ],
    }
    assert member_keys_from_group(group) == {"swannobi", "iron morph"}


def test_empty_wom_group():
    assert member_keys_from_group({"name": "Ugandans"}) == frozenset()


# ---- the Dink settings file (served publicly from GitHub, so it must never hold a webhook)


def test_dink_settings_have_no_webhooks():
    settings = json.loads(DINK_SETTINGS.read_text())
    webhook_keys = [key for key in settings if key.lower().endswith("webhook")]
    assert not webhook_keys, f"webhook settings in a public file: {webhook_keys}"
    assert not re.search(r"discord(app)?\.com/api/webhooks", DINK_SETTINGS.read_text())
    # Dink ignores this key on import anyway, but pointing at ourselves would just be confusing
    assert "dynamicConfigUrl" not in settings
    # Deaths are each player's choice (/osrs register asks). Dink re-imports these settings every few hours,
    # so a shared "deathEnabled" would switch deaths back on for people who said no.
    assert "deathEnabled" not in settings


# ---- the flexing kit


def test_kit_without_deaths():
    kit = flexing.build_kit("https://example.com/main-hook", None)
    assert "https://example.com/main-hook" in kit
    assert lines.DINK_SETTINGS_URL in kit
    assert lines.FLEX_KIT_NO_DEATHS in kit  # untick Enable Death, empty overrides
    assert len(kit) < 2000  # Discord's message limit


def test_kit_with_deaths():
    kit = flexing.build_kit("https://example.com/main-hook", "https://example.com/deaths-hook")
    assert "https://example.com/deaths-hook" in kit
    assert lines.FLEX_KIT_NO_DEATHS not in kit
    # the whole register message (intro + answers + kit + the clan question) must fit in one Discord message
    worst_case = "\n".join(
        [lines.REGISTERED.format(rsn="x" * 12) + lines.REGISTERED_DEFAULT, lines.FLEX_YES, lines.DEATHS_YES, kit]
        + [lines.CLAN_JOIN.format(clan=lines.CLAN_NAME)]
    )
    assert (
        len(worst_case.replace("https://example.com/", "https://discord.com/api/webhooks/" + "9" * 19 + "/" + "x" * 68))
        < 2000
    )


# ---- database: osrs_accounts


async def test_first_account_is_the_default_and_alts_are_not(db):
    assert await db.add_osrs_account(ALICE, "Swannobi", "swannobi") is None
    assert await db.add_osrs_account(ALICE, "Iron Swan", "iron swan") is None
    accounts = await db.get_osrs_accounts(ALICE)
    assert [(a.rsn, a.is_default) for a in accounts] == [("Swannobi", True), ("Iron Swan", False)]


async def test_a_name_can_only_be_claimed_once(db):
    await db.add_osrs_account(ALICE, "Swannobi", "swannobi")
    assert await db.add_osrs_account(ALICE, "swannobi", "swannobi") == ALICE  # already yours
    assert await db.add_osrs_account(BOB, "SWANNOBI", "swannobi") == ALICE  # Alice has it
    assert await db.get_osrs_accounts(BOB) == []


async def test_changing_the_default(db):
    await db.add_osrs_account(ALICE, "Main", "main")
    await db.add_osrs_account(ALICE, "Alt", "alt")
    assert await db.set_default_osrs_account(ALICE, "alt")
    accounts = await db.get_osrs_accounts(ALICE)
    assert accounts[0].rsn == "Alt" and accounts[0].is_default
    assert not accounts[1].is_default
    assert not await db.set_default_osrs_account(BOB, "alt")  # not Bob's


async def test_removing_the_default_promotes_the_oldest_alt(db):
    for name in ("Main", "Alt One", "Alt Two"):
        await db.add_osrs_account(ALICE, name, name.lower())
    assert await db.remove_osrs_account(ALICE, "main")
    accounts = await db.get_osrs_accounts(ALICE)
    assert [(a.rsn, a.is_default) for a in accounts] == [("Alt One", True), ("Alt Two", False)]


async def test_removing_someone_elses_account_does_nothing(db):
    await db.add_osrs_account(ALICE, "Main", "main")
    assert not await db.remove_osrs_account(BOB, "main")
    assert len(await db.get_osrs_accounts(ALICE)) == 1


async def test_clan_answers(db):
    await db.add_osrs_account(ALICE, "Main", "main")
    await db.set_clan_answer(ALICE, "main", "member")
    assert (await db.get_osrs_accounts(ALICE))[0].clan_answer == "member"
    with pytest.raises(ValueError):
        await db.set_clan_answer(ALICE, "main", "maybe")


# ---- database: osrs_flexers


async def test_flexers_are_remembered_once(db):
    assert not await db.is_flexer(ALICE)
    await db.add_flexer(ALICE)
    await db.add_flexer(ALICE)
    await db.add_flexer(BOB)
    assert await db.is_flexer(ALICE)
    assert sorted(await db.get_flexers()) == [ALICE, BOB]


def test_flexing_off_when_not_configured(monkeypatch, caplog):
    monkeypatch.delenv("OSRS_FLEXING_CHANNEL_ID", raising=False)
    monkeypatch.delenv("OSRS_DEATHS_CHANNEL_ID", raising=False)
    bot = types.SimpleNamespace(get_channel=lambda channel_id: None)
    flexing.log_settings(bot)  # must not raise: the bot has to start with flexing unconfigured
    assert "flexing is off" in caplog.text
    with pytest.raises(flexing.FlexingNotSetUp):
        flexing.flexing_channels(bot)


def test_bad_channel_id_switches_flexing_off(monkeypatch, caplog):
    monkeypatch.setenv("OSRS_FLEXING_CHANNEL_ID", "not-a-number")
    bot = types.SimpleNamespace(get_channel=lambda channel_id: None)
    flexing.log_settings(bot)
    assert "isn't a text channel" in caplog.text
    with pytest.raises(flexing.FlexingNotSetUp):
        flexing.flexing_channels(bot)
