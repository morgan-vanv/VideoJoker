"""How /help is laid out: the one file to edit to change the order of things, what each area says, and which
commands it lists. /help's tour, its topic pages and its "Every command" page are all built from this list
(guide/pages.py), so they can't disagree.

Morgan's order (2026-11-16): the essentials first (music, your own voice channel, OSRS, Minecraft), then the
nice-to-haves (XP and money, games, raffles).

How to write the text: put commands in backticks with their slash, like `/play` or `/mc register`. /help turns
them into blue links that fill the command into your chat box when tapped. {lobby} is the personal-VC lobby as a
link, {ladder} this server's ranks, and {shout} the /mc shout bit (only while the booth is on). tests/test_guide.py checks every command named here really exists, and that every command a member can
run is listed somewhere, so nothing goes missing from /help when commands change.
"""

from typing import NamedTuple

from core.database import COMMAND_XP_COOLDOWN_SECONDS, USH_PER_MESSAGE, XP_PER_COMMAND, XP_PER_MESSAGE
from minecraft.server import ADDRESS
from minecraft.shout import PER_PERSON_SECONDS, SHOUT_COST
from music.player import IDLE_TIMEOUT
from standing.lines import cooldown_words


class Cmd(NamedTuple):
    name: str  # as you'd type it, without the slash: "play", "mc register"
    what: str  # one short line, shown next to it on the topic pages
    needs: str = ""  # "booth": only listed when the Minecraft booth is switched on


class Area(NamedTuple):
    key: str  # the dropdown's value (never shown)
    emoji: str
    name: str
    tour: str  # what the tour says (the main areas get a heading and this; the others just this, on one line)
    commands: list[Cmd]
    cogs: tuple[str, ...]  # the area only shows when these cogs are running
    main: bool  # True: near the top of the tour, with a heading. False: a one-liner at the bottom.
    intro: str = ""  # the topic page's first line, above the commands
    note: str = ""  # small grey print at the bottom of the topic page


XP_EARNED = (
    f"Every message earns {XP_PER_MESSAGE} XP and {USH_PER_MESSAGE} USh, and every command {XP_PER_COMMAND} XP "
    f"({cooldown_words(COMMAND_XP_COOLDOWN_SECONDS)}). XP never resets."
)

AREAS = [
    Area(
        key="music",
        emoji="🎵",
        name="Music",
        tour=(
            "Join a voice channel, then `/play` a song name or a YouTube, SoundCloud, Spotify or Tidal link. "
            "The now-playing card has the buttons."
        ),
        intro="Join a voice channel first.",
        commands=[
            Cmd("play", "A song name or a link. `play_next` puts it at the front of the queue."),
            Cmd("skip", "On to the next song."),
            Cmd("queue", "What's coming up. `remove` takes a song out."),
            Cmd("nowplaying", "The card with the buttons: pause, skip, stop, shuffle, loop and the queue."),
            Cmd("volume", "0 to 200%."),
            Cmd("leave", "Sends me home and clears the queue."),
        ],
        note=f"I leave by myself after {IDLE_TIMEOUT // 60} minutes with nothing to play.",
        cogs=("Music",),
        main=True,
    ),
    Area(
        key="voice",
        emoji="🔊",
        name="Your own voice channel",
        tour=(
            "Join {lobby} and I'll make you a channel of your own. "
            "Buttons in its chat open it, lock it, hide it, or let guests in."
        ),
        intro=(
            "Join {lobby} and I'll make you a channel of your own and move you in. It's yours until the last "
            "person leaves. No commands: the buttons in its chat (only you can use them) do it all.\n"
            "🔓 **Open** · 🔒 **Locked**: everyone sees it, only guests join · 👻 **Hidden**: only guests see it\n"
            "➕ **Let in** · ➖ **Remove** guests"
        ),
        commands=[],
        note="Your mode and guest list are remembered for next time.",
        cogs=("PersonalVC",),
        main=True,
    ),
    Area(
        key="osrs",
        emoji="⚔️",
        name="Old School RuneScape",
        tour="Link your accounts with `/osrs register` and flex your drops.",
        commands=[
            Cmd("osrs register", "Link an account (alts welcome)."),
            Cmd("osrs accounts", "Your accounts: pick your main, or unlink one. Only you see it."),
            Cmd("osrs whois", "Which accounts someone plays."),
            Cmd("osrs flexing", "What to paste into Dink to flex your drops."),
        ],
        cogs=("Osrs",),
        main=True,
    ),
    Area(
        key="minecraft",
        emoji="⛏️",
        name="Minecraft",
        tour=(
            f"`{ADDRESS}`, Java and Bedrock. Link your account with `/mc register`, "
            "see who's on with `/mc status`{shout}."
        ),
        intro=f"`{ADDRESS}` · Java and Bedrock.",
        commands=[
            Cmd("mc register", "Link a Java or Bedrock account, then see how to join."),
            Cmd("mc accounts", "Your accounts: pick your main, or unlink one. Only you see it."),
            Cmd("mc whois", "Pick a member to see what they play, or type a name to see who plays it."),
            Cmd("mc status", "Is the server up, and who's on?"),
            Cmd(
                "mc shout",
                f"Shout into the game's chat ({SHOUT_COST} USh, {cooldown_words(PER_PERSON_SECONDS)}).",
                needs="booth",
            ),
        ],
        cogs=("Minecraft",),
        main=True,
    ),
    Area(
        key="standing",
        emoji="🎖️",
        name="XP, ranks and USh",
        tour="Chat to earn XP and USh{ladder}: `/profile` `/pay` `/leaderboard`",
        intro=XP_EARNED + "{ladder_sentence} USh is the server's play money.",
        commands=[
            Cmd("profile", "Your rank, the ladder, XP, USh, payments and game accounts. Or someone else's."),
            Cmd("pay", "Send someone USh, with a note if you like."),
            Cmd("leaderboard", "The server's top 10, by XP or by USh."),
        ],
        cogs=("Utility", "Economy"),
        main=False,
    ),
    Area(
        key="games",
        emoji="🎲",
        name="Games and fun",
        tour="Games: `/roll` `/coinflip` `/8ball` `/threecardmonte` and more",
        commands=[
            Cmd("roll", "Dice: one six-sided die, or pick the sides and how many."),
            Cmd("coinflip", "Heads or tails."),
            Cmd("8ball", "Ask it a yes-or-no question."),
            Cmd("rockpaperscissors", "Against me."),
            Cmd("threecardmonte", "Find the winning card before the dealer packs up."),
            Cmd("russianroulette", "Feeling lucky?"),
            Cmd("curseofra", "shut up, bozo."),
            Cmd("say", "I'll repeat after you."),
        ],
        cogs=("Games", "Fun"),
        main=False,
    ),
    Area(
        key="raffle",
        emoji="🎟️",
        name="Raffles",
        tour="Give something away: `/raffle start`",
        intro="People react 🎟️ on the raffle to enter, and a winner is drawn when time's up.",
        commands=[
            Cmd("raffle start", "Put up a prize, for 1 minute to 7 days."),
            Cmd("raffle end", "Draw your raffle now."),
            Cmd("raffle cancel", "Call off your raffle."),
        ],
        cogs=("Raffle",),
        main=False,
    ),
]

# Commands a member can run that don't belong on a page: /help itself
NOT_LISTED = {"help"}
