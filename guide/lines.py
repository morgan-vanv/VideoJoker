"""The VJ's words for /help. Every line of the tour lives here, so the voice stays in one place (same idea as
standing/lines.py and personal_vc/lines.py).

The XP and USh numbers are built from core/database.py, so the tour can't promise more (or less) than the bot
actually hands out. tests/test_guide.py fails if any line here mentions a slash command that doesn't exist.
"""

from core.database import COMMAND_XP_COOLDOWN_SECONDS, USH_PER_MESSAGE, XP_PER_COMMAND, XP_PER_MESSAGE
from standing.lines import cooldown_words

TITLE = "🎬 Welcome to the show, comrade. I'm VideoJoker."

# Morgan's words, word for word
DESCRIPTION = (
    "I'm this server's bot, use me to play music and do dope stuff. "
    "All you gotta do is: type `/` in any chat and pick a command."
)
# Added under the description when /help is run in DMs, where the server-only commands won't work
IN_DMS = "🎞️ You're in my DMs, comrade: most of this only works in the server, so head back there to try it."

# Morgan's words, word for word: the footer, the card's last line. (Footers can't show `code`, so no backticks.)
LAST_LINE = "For the rest of the commands: /listcommands"

# "Every message earns 1 XP, and every command 5 (once a minute)."
XP_EARNED = (
    f"Every message earns {XP_PER_MESSAGE} XP, and every command {XP_PER_COMMAND} "
    f"({cooldown_words(COMMAND_XP_COOLDOWN_SECONDS)})."
)

RANKS_NAME = "🎖️ XP and ranks"


def ranks_text(rank_names: list[str]) -> str:
    """The XP and ranks section, with this server's ranks from lowest to highest (LOWLY SERFS → ... → LORDS)."""
    ladder = " → ".join(rank_names)
    return (
        f"{XP_EARNED} XP never resets, and it moves you up the ranks: **{ladder}**. See where you stand with `/rank`."
    )


USH_NAME = "💰 USh, the server's play money"
USH_TEXT = (
    f"You get {USH_PER_MESSAGE} USh for every message. Check your wallet with `/balance`, "
    "and send some to a friend with `/pay`."
)

LEADERBOARD_NAME = "🏆 Leaderboard"
LEADERBOARD_TEXT = "`/leaderboard` shows the server's top 10, by XP or by USh."
# Added to the leaderboard section when there's no ranks section to explain XP (no ladder on this server)
XP_WITHOUT_RANKS = f"{XP_EARNED} Check yours with `/rank`."

MUSIC_NAME = "🎵 Music"
MUSIC_TEXT = (
    "Join a voice channel, then `/play` a song name or a YouTube, SoundCloud, Spotify or Tidal link. "
    "The now-playing card has buttons to pause, skip and more."
)

PERSONAL_VC_NAME = "🔊 Your own voice channel"
# {lobby} is the lobby as a channel mention (<#id>): Discord shows it as a link you can click
PERSONAL_VC_TEXT = (
    "Join {lobby} and I'll make you a channel of your own. "
    "Buttons in its chat open it, lock it, hide it, or let guests in."
)

GAMES_NAME = "🎲 Games and fun"
GAMES_TEXT = "`/threecardmonte`, `/coinflip`, `/8ball`, `/roast` and friends."

OSRS_NAME = "⚔️ Old School RuneScape"
OSRS_TEXT = "Link your accounts with `/osrs register` and flex your drops."
