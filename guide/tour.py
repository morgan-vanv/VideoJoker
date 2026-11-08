"""Which sections the /help card shows, worked out from plain facts with no Discord in sight, so tests can try
every combination (tests/test_guide.py). The cog (cogs/guide.py) looks the facts up; this file decides.

The rule: a section only shows when its feature is really on here. A cog that isn't loaded, a server without a
rank ladder, or personal voice channels that were never set up (or whose lobby was deleted) all drop their
section, so a new member is never pointed at something that won't work. In DMs there's no server to look up, so
the cog passes None for the ranks and the lobby, and only the general sections are left.
"""

from typing import Collection, NamedTuple, Optional

from guide import lines


class Section(NamedTuple):
    """One field on the /help card."""

    name: str  # the field's heading, e.g. "🎵 Music"
    text: str  # what it says underneath


def pick_sections(loaded_cogs: Collection[str], ranks: Optional[list[str]], lobby: Optional[str]) -> list[Section]:
    """The /help card's sections, in order, leaving out the features that aren't on.

    loaded_cogs: the names of the cogs that are running (the keys of bot.cogs), e.g. {"Music", "Economy", ...}
    ranks: this server's rank names, lowest first, or None when there's no ladder (or no server: a DM)
    lobby: the personal-VC lobby as a channel mention ("<#123>"), or None when it's off (or a DM)
    """

    def loaded(*cog_names: str) -> bool:
        return all(name in loaded_cogs for name in cog_names)

    sections = []

    # /ladder lives in the Ranks cog, /rank in Utility: the section needs both, and a ladder on this server
    show_ranks = bool(ranks) and loaded("Ranks", "Utility")
    if show_ranks:
        sections.append(Section(lines.RANKS_NAME, lines.ranks_text(ranks)))

    if loaded("Economy"):
        sections.append(Section(lines.USH_NAME, lines.USH_TEXT))

    if loaded("Utility"):
        # The leaderboard counts XP. Without the ranks section nothing else says how XP is earned, so say it here
        text = lines.LEADERBOARD_TEXT if show_ranks else f"{lines.LEADERBOARD_TEXT} {lines.XP_WITHOUT_RANKS}"
        sections.append(Section(lines.LEADERBOARD_NAME, text))

    if loaded("Music"):
        sections.append(Section(lines.MUSIC_NAME, lines.MUSIC_TEXT))

    if lobby is not None and loaded("PersonalVC"):
        sections.append(Section(lines.PERSONAL_VC_NAME, lines.PERSONAL_VC_TEXT.format(lobby=lobby)))

    # The games are in the Games cog, /roast is in Fun
    if loaded("Games", "Fun"):
        sections.append(Section(lines.GAMES_NAME, lines.GAMES_TEXT))

    if loaded("Osrs"):
        sections.append(Section(lines.OSRS_NAME, lines.OSRS_TEXT))

    return sections
