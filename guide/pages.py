"""The words on each /help page, built from guide/layout.py and what's switched on here, with no Discord in sight
so tests can try every combination (tests/test_guide.py). cogs/guide.py looks the facts up and lays the pages
out on screen.

The rule from before stays: an area only shows when its feature is really on here. A cog that isn't running,
personal voice channels with no lobby, or the Minecraft booth switched off (for /mc shout) all drop out, so a
new member is never pointed at something that won't work.
"""

import re
from typing import NamedTuple, Optional

from guide import lines
from guide.layout import AREAS, Area, Cmd


class Facts(NamedTuple):
    """What's on where /help was run."""

    cogs: frozenset[str]  # the names of the cogs that are running
    ranks: Optional[list[str]]  # this server's rank names, lowest first, or None (no ladder, or a DM)
    lobby: Optional[str]  # the personal-VC lobby as a channel link ("<#123>"), or None (off, or a DM)
    booth: bool  # the Minecraft booth is on (so /mc shout works)


def areas_on(facts: Facts) -> list[Area]:
    """The areas to show, in the layout's order."""
    shown = []
    for area in AREAS:
        if not all(cog in facts.cogs for cog in area.cogs):
            continue
        if area.key == "voice" and facts.lobby is None:
            continue
        shown.append(area)
    return shown


def commands_of(area: Area, facts: Facts) -> list[Cmd]:
    return [cmd for cmd in area.commands if cmd.needs != "booth" or facts.booth]


def fill(text: str, facts: Facts) -> str:
    """Puts this server's lobby and ladder into an area's text."""
    ladder = " → ".join(facts.ranks) if facts.ranks else ""
    return text.format(
        lobby=facts.lobby or "",
        ladder=f" and climb **{ladder}**" if ladder else "",
        ladder_sentence=f" It moves you up the ranks: **{ladder}**." if ladder else "",
        shout=", and `/mc shout` into the game" if facts.booth else "",
    )


def tour(facts: Facts, in_dms: bool) -> list[str]:
    """The tour, as blocks of text with a divider between them: the welcome, the main areas, the one-liners."""
    welcome = f"## {lines.TITLE}\n{lines.DESCRIPTION}"
    if in_dms:
        welcome += f"\n\n{lines.IN_DMS}"
    shown = areas_on(facts)
    main = [f"### {area.emoji} {area.name}\n{fill(area.tour, facts)}" for area in shown if area.main]
    extras = [f"{area.emoji} {fill(area.tour, facts)}" for area in shown if not area.main]
    blocks = [welcome, "\n\n".join(main)]
    if extras:
        blocks.append("\n".join(extras) + f"\n-# {lines.LAST_LINE}")
    else:
        blocks.append(f"-# {lines.LAST_LINE}")
    return [block for block in blocks if block]


def command_line(cmd: Cmd) -> str:
    return f"`/{cmd.name}` {cmd.what}"


def topic(area: Area, facts: Facts) -> str:
    """One area's page: what it is, every command with a line on each, and any small print."""
    parts = [f"## {area.emoji} {area.name}"]
    if area.intro:
        parts.append(fill(area.intro, facts))
    parts += [command_line(cmd) for cmd in commands_of(area, facts)]
    if area.note:
        parts.append(f"-# {area.note}")
    return "\n".join(parts)


def everything(facts: Facts) -> str:
    """Every command in one page, area by area (what /listcommands used to be)."""
    parts = [f"## {lines.EVERYTHING_TITLE}"]
    for area in areas_on(facts):
        commands = commands_of(area, facts)
        parts.append(f"### {area.emoji} {area.name}")
        if commands:
            parts += [command_line(cmd) for cmd in commands]
        else:
            parts.append(fill(area.tour, facts))
    return "\n".join(parts)


# `/play`, `/mc register`: a slash command in backticks, as layout.py writes them
COMMAND_IN_TEXT = re.compile(r"`/([a-z0-9][\w-]*(?: [a-z0-9][\w-]*)?)`")


def clickable(text: str, command_ids: dict[str, int]) -> str:
    """Turns `/play` into </play:123>, which Discord shows as a blue link that fills the command into your chat box.
    It needs the command's ID from Discord (bot.command_ids, filled in when commands sync); without one it stays
    as code."""

    def link(match: re.Match) -> str:
        full = match.group(1)
        command_id = command_ids.get(full.split(" ")[0])
        return f"</{full}:{command_id}>" if command_id else match.group(0)

    return COMMAND_IN_TEXT.sub(link, text)
