"""Tests for /help: which sections show (guide/tour.py), and a guard that its words (guide/lines.py) only ever
mention slash commands that really exist."""

import re

from guide import lines
from guide.tour import pick_sections
from tests.real_commands import build_bot, commands_by_name

EVERY_COG = {"Games", "Fun", "Utility", "Permissions", "Music", "Economy", "Ranks", "Heartbeat", "Osrs", "PersonalVC"}
RANKS = ["LOWLY SERFS", "SWORN SWORDS", "LORDS"]
LOBBY = "<#777>"


def headings(sections) -> list[str]:
    return [section.name for section in sections]


# ---- Which sections show


def test_everything_on_shows_every_section_in_order():
    assert headings(pick_sections(EVERY_COG, RANKS, LOBBY)) == [
        lines.RANKS_NAME,
        lines.USH_NAME,
        lines.LEADERBOARD_NAME,
        lines.MUSIC_NAME,
        lines.PERSONAL_VC_NAME,
        lines.GAMES_NAME,
        lines.OSRS_NAME,
    ]


def test_ranks_section_names_the_ladder_lowest_first():
    ranks = pick_sections(EVERY_COG, RANKS, LOBBY)[0]
    assert "**LOWLY SERFS → SWORN SWORDS → LORDS**" in ranks.text
    assert "1 XP" in ranks.text and "every command 5 (once a minute)" in ranks.text


def test_no_ladder_drops_ranks_but_the_leaderboard_still_explains_xp():
    sections = pick_sections(EVERY_COG, None, LOBBY)
    assert lines.RANKS_NAME not in headings(sections)
    leaderboard = next(section for section in sections if section.name == lines.LEADERBOARD_NAME)
    assert lines.XP_EARNED in leaderboard.text
    assert "SERFS" not in "".join(section.text for section in sections)


def test_with_a_ladder_xp_is_explained_once():
    sections = pick_sections(EVERY_COG, RANKS, LOBBY)
    assert sum(lines.XP_EARNED in section.text for section in sections) == 1


def test_ranks_cog_not_loaded_drops_ranks_even_with_a_ladder():
    assert lines.RANKS_NAME not in headings(pick_sections(EVERY_COG - {"Ranks"}, RANKS, LOBBY))


def test_personal_vc_off_drops_its_section():
    assert lines.PERSONAL_VC_NAME not in headings(pick_sections(EVERY_COG, RANKS, None))


def test_personal_vc_section_links_the_lobby():
    section = next(s for s in pick_sections(EVERY_COG, RANKS, LOBBY) if s.name == lines.PERSONAL_VC_NAME)
    assert section.text.startswith("Join <#777> and I'll make you a channel of your own.")


def test_personal_vc_cog_not_loaded_drops_its_section():
    assert lines.PERSONAL_VC_NAME not in headings(pick_sections(EVERY_COG - {"PersonalVC"}, RANKS, LOBBY))


def test_dms_show_only_the_general_sections():
    # In DMs the cog has no server to look up, so it passes None for both
    assert headings(pick_sections(EVERY_COG, None, None)) == [
        lines.USH_NAME,
        lines.LEADERBOARD_NAME,
        lines.MUSIC_NAME,
        lines.GAMES_NAME,
        lines.OSRS_NAME,
    ]


def test_missing_cogs_drop_their_sections():
    assert headings(pick_sections({"Music", "Heartbeat"}, RANKS, LOBBY)) == [lines.MUSIC_NAME]
    assert pick_sections(set(), RANKS, LOBBY) == []


def test_morgans_words_stay_word_for_word():
    assert lines.DESCRIPTION == (
        "I'm this server's bot, use me to play music and do dope stuff. "
        "All you gotta do is: type `/` in any chat and pick a command."
    )
    assert lines.LAST_LINE == "For the rest of the commands: /listcommands"


# ---- The guard: /help never points at a command that doesn't exist

# "/rank", "/osrs register", ... A slash, a command name, then maybe one more word (a subcommand, or just the next
# word of the sentence: "/play a song"). Not after a letter, ":" or "/", so links (https://...) don't count.
MENTION = re.compile(r"(?<![\w:/])/([a-z0-9][\w-]*)(?: ([a-z0-9][\w-]*))?")


def every_help_text() -> list[str]:
    """All the words /help can show: every line in guide/lines.py, plus the sections as built (both ways)."""
    texts = [value for name, value in vars(lines).items() if isinstance(value, str) and not name.startswith("__")]
    for ranks in (RANKS, None):
        texts += [section.text for section in pick_sections(EVERY_COG, ranks, LOBBY)]
    return texts


async def test_help_only_mentions_commands_that_exist():
    real = commands_by_name(build_bot())
    mentions = [match for text in every_help_text() for match in MENTION.findall(text)]
    assert len(mentions) >= 10  # the regex is finding the mentions at all

    for first, second in mentions:
        # "/osrs register" must be a real subcommand. "/play a" isn't one, so then "/play" itself must be real.
        found = f"{first} {second}" in real or first in real
        assert found, f"/help mentions /{first} {second}".strip() + ", but there's no such command"


async def test_the_guard_catches_a_made_up_command():
    real = commands_by_name(build_bot())
    ((first, second),) = MENTION.findall("Try `/osrs flex` today")
    assert f"{first} {second}" not in real and first not in real  # /osrs alone is a group: can't be run
