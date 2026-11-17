"""Tests for /help: which areas show and what each page says (guide/pages.py, built from guide/layout.py), the
guards that keep it honest against the real commands, and the page on screen (cogs/guide.py) within Discord's
limits."""

import re

import discord

from bot import runnable_commands
from cogs.guide import HelpView, page_blocks
from cogs.permissions import is_vip_command
from guide import lines
from guide.layout import AREAS, NOT_LISTED
from guide.pages import Facts, areas_on, clickable, everything, topic, tour
from tests.real_commands import build_bot, commands_by_name

EVERY_COG = frozenset(
    {"Games", "Fun", "Utility", "Permissions", "Music", "Economy", "Ranks", "Osrs", "PersonalVC", "Minecraft", "Raffle"}
)
RANKS = ["LOWLY SERFS", "SWORN SWORDS", "LORDS"]
LOBBY = "<#777>"
ALL_ON = Facts(EVERY_COG, RANKS, LOBBY, booth=True)


def keys(facts: Facts) -> list[str]:
    return [area.key for area in areas_on(facts)]


# ---- Which areas show, and in what order


def test_everything_on_shows_morgans_order():
    assert keys(ALL_ON) == ["music", "voice", "osrs", "minecraft", "standing", "games", "raffle"]


def test_the_essentials_get_headings_and_the_rest_one_line_each():
    welcome, main, extras = tour(ALL_ON, in_dms=False)
    assert welcome.startswith(f"## {lines.TITLE}\n{lines.DESCRIPTION}")
    headings = re.findall(r"^### (.+)$", main, flags=re.M)
    assert headings == ["🎵 Music", "🔊 Your own voice channel", "⚔️ Old School RuneScape", "⛏️ Minecraft"]
    assert extras.splitlines()[0].startswith(
        "🎖️ Chat to earn XP and USh and climb **LOWLY SERFS → SWORN SWORDS → LORDS**"
    )
    assert extras.endswith(f"-# {lines.LAST_LINE}")


def test_features_that_are_off_drop_out():
    assert "voice" not in keys(ALL_ON._replace(lobby=None))  # no lobby here (or a DM)
    assert "music" not in keys(ALL_ON._replace(cogs=EVERY_COG - {"Music"}))
    assert keys(ALL_ON._replace(cogs=frozenset())) == []
    no_ladder = tour(ALL_ON._replace(ranks=None), in_dms=False)[2]
    assert "SERFS" not in no_ladder and "Chat to earn XP and USh: `/profile`" in no_ladder


def test_mc_shout_only_shows_while_the_booth_is_on():
    minecraft = next(area for area in AREAS if area.key == "minecraft")
    assert "`/mc shout`" in topic(minecraft, ALL_ON) and "`/mc shout`" in tour(ALL_ON, False)[1]
    off = ALL_ON._replace(booth=False)
    assert "/mc shout" not in topic(minecraft, off) and "/mc shout" not in tour(off, False)[1]
    assert "/mc shout" not in everything(off)


def test_dms_get_the_dm_line():
    assert lines.IN_DMS in tour(Facts(EVERY_COG, None, None, False), in_dms=True)[0]
    assert lines.IN_DMS not in tour(ALL_ON, in_dms=False)[0]


def test_morgans_words_stay_word_for_word():
    assert lines.DESCRIPTION == (
        "I'm this server's bot, use me to play music and do dope stuff. "
        "All you gotta do is: type `/` in any chat and pick a command."
    )


def test_the_lobby_and_ladder_are_filled_in():
    voice = next(area for area in AREAS if area.key == "voice")
    assert LOBBY in topic(voice, ALL_ON) and "{lobby}" not in topic(voice, ALL_ON)
    standing = next(area for area in AREAS if area.key == "standing")
    assert "It moves you up the ranks: **LOWLY SERFS → SWORN SWORDS → LORDS**." in topic(standing, ALL_ON)
    assert "{" not in everything(ALL_ON)


# ---- Tappable commands


def test_commands_become_links_when_their_id_is_known():
    ids = {"play": 11, "mc": 22}
    assert clickable("Try `/play` and `/mc register`.", ids) == "Try </play:11> and </mc register:22>."
    assert clickable("Try `/skip`.", ids) == "Try `/skip`."  # no ID yet: stays as code
    assert clickable("`mc.morganvanv.com`", ids) == "`mc.morganvanv.com`"  # not a command


# ---- The guards: /help matches the real commands


async def test_help_only_names_commands_that_exist():
    real = commands_by_name(build_bot())
    texts = [everything(ALL_ON)] + tour(ALL_ON, False) + [topic(area, ALL_ON) for area in AREAS]
    texts += [value for value in vars(lines).values() if isinstance(value, str)]
    named = {match for text in texts for match in re.findall(r"`/([a-z0-9][\w-]*(?: [a-z0-9][\w-]*)?)`", text)}
    assert len(named) >= 25
    for name in named:
        assert name in real, f"/help names /{name}, but there's no such command"


async def test_every_command_a_member_can_run_is_on_a_help_page():
    """/help replaced /listcommands, so it must list every command a member can run: a new command that nobody
    adds to guide/layout.py fails here."""
    bot = build_bot()
    members_can_run = {
        cmd.qualified_name
        for cmd in runnable_commands(bot.tree)
        if not is_vip_command(cmd) and cmd.qualified_name.split(" ")[0] != "setup"
    }
    listed = {cmd.name for area in AREAS for cmd in area.commands}
    assert members_can_run - NOT_LISTED == listed


# ---- On screen


async def test_every_page_fits_in_discords_limits():
    ids = {name: 1234567890123456789 for name in commands_by_name(build_bot())}
    for choice in ["tour", "all"] + [area.key for area in AREAS]:
        view = HelpView(page_blocks(choice, ALL_ON, False), ALL_ON, ids, False)
        text = "".join(item.content for item in view.walk_children() if isinstance(item, discord.ui.TextDisplay))
        assert len(text) <= 4000, choice  # Discord: 4,000 characters of text per message in this layout
        assert view.total_children_count <= 40, choice  # and 40 components


async def test_the_dropdown_offers_the_tour_every_area_that_is_on_and_everything():
    view = HelpView(tour(ALL_ON, False), ALL_ON, {}, False)
    picker = next(item for item in view.walk_children() if isinstance(item, discord.ui.Select))
    assert [option.value for option in picker.options] == ["tour"] + keys(ALL_ON) + ["all"]
