"""Reading the servers' log files: who joined the network (Velocity's log), who died or earned an advancement
(Factions' log). The files are mounted read-only into the booth; we only ever read them.

Two rules from the infra side, both kept here:
- Velocity's "has connected" line also holds the player's IP address. We take the name and drop the rest of the
  line on the spot: the IP is never stored, logged or sent anywhere.
- Player chat is never read out. Chat lines start with "<Name>", so nothing here ever matches them.
"""

import asyncio
import os
import re
from typing import AsyncIterator, Optional


# Every log line starts with a time and a level, then up to two more bracketed bits, and we want what comes after:
#   "[12:34:56 INFO]: ..."                                    the console's style
#   "[12:34:56] [Server thread/INFO]: ..."                   Paper's latest.log (thread/level)
#   "[12:34:56] [Netty epoll Worker #3/INFO] [com.velocitypowered...ConnectedPlayer]: ..."
#                                                            Velocity's latest.log (thread/level, then the logger)
# Velocity's file layout was found by the infra side's review (2026-11-16): with only one bracketed bit allowed,
# no Velocity line matched and first joins never reached the bot.
_PREFIX = re.compile(r"^\[[\d:.]+(?: [A-Z]+)?\](?: \[[^\]]+\]){0,2}: (.*)$")
_VELOCITY_JOIN = re.compile(r"^\[connected player\] (.+?) \(/[^)]*\) has connected$")
_ADVANCEMENT = re.compile(r"^(.+?) has (?:made the advancement|completed the challenge|reached the goal) \[(.+)\]$")
_JOINED_GAME = re.compile(r"^(.+?) joined the game$")
# How vanilla death messages continue after the player's name ("Steve was slain by Zombie", "Steve drowned"...)
DEATH_STARTS = (
    "was ",
    "drowned",
    "died",
    "experienced kinetic energy",
    "fell ",
    "hit the ground",
    "burned",
    "went up in flames",
    "went off with a bang",
    "walked into",
    "tried to swim in lava",
    "discovered the floor was lava",
    "starved",
    "suffocated",
    "froze",
    "withered away",
    "left the confines",
    "didn't want to live",
    "blew up",
)


def message(line: str) -> Optional[str]:
    """The message part of a log line, or None if it isn't a normal log line."""
    match = _PREFIX.match(line.strip())
    return match.group(1) if match else None


def velocity_join(msg: str) -> Optional[str]:
    """The player's name from Velocity's "[connected player] Name (/ip:port) has connected", or None.
    Only the name comes out of here: the address in the brackets is dropped."""
    match = _VELOCITY_JOIN.match(msg)
    return match.group(1) if match else None


def joined_game(msg: str) -> Optional[str]:
    """A Paper server's "Name joined the game" (we use it to learn who's around, never as a postcard)."""
    if msg.startswith(("<", "[", "*")):
        return None
    match = _JOINED_GAME.match(msg)
    return match.group(1) if match else None


def advancement(msg: str) -> Optional[tuple[str, str]]:
    """(name, advancement title) from "Name has made the advancement [Stone Age]", or None."""
    if msg.startswith(("<", "[", "*")):  # chat, /say and /me lines can't fake one
        return None
    match = _ADVANCEMENT.match(msg)
    return (match.group(1), match.group(2)) if match else None


def death(msg: str, known_names: set[str]) -> Optional[str]:
    """The player's name if this is a death message for someone we know is on the server, or None.

    Death messages have no fixed shape ("Steve drowned", "Steve was shot by Skeleton"), so we check two things:
    the line starts with the name of a player who's on the server, and what follows starts like a death message.
    """
    if msg.startswith(("<", "[", "*")):
        return None
    for name in known_names:
        if msg.startswith(name + " ") and msg[len(name) + 1 :].startswith(DEATH_STARTS):
            return name
    return None


async def follow(path: str, poll_seconds: float = 1.0) -> AsyncIterator[str]:
    """Yields each new line written to a log file, like `tail -F`, forever.

    It starts at the end (old lines were before our time), waits while the file doesn't exist (a sleeping mode),
    and starts over from the top when the file is replaced or cut short: Minecraft starts a fresh latest.log
    every time a server starts.
    """
    handle = None
    inode = None
    buffer = ""
    first_open = True
    try:
        while True:
            try:
                stat = os.stat(path)
            except FileNotFoundError:
                await asyncio.sleep(poll_seconds)
                continue
            if handle is None or stat.st_ino != inode or stat.st_size < handle.tell():
                if handle is not None:
                    handle.close()
                handle = open(path, encoding="utf-8", errors="replace")  # pylint: disable=consider-using-with
                inode = stat.st_ino
                buffer = ""
                if first_open:
                    handle.seek(0, os.SEEK_END)
                first_open = False
            chunk = handle.read()
            if not chunk:
                await asyncio.sleep(poll_seconds)
                continue
            buffer += chunk
            *lines, buffer = buffer.split("\n")  # the last piece may be a line still being written
            for line in lines:
                yield line.rstrip("\r")
    finally:
        if handle is not None:
            handle.close()
