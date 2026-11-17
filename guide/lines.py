"""The VJ's words for /help that aren't about one area: the welcome, the DM line, the last line and the dropdown.
What each area says lives in guide/layout.py. tests/test_guide.py fails if anything here or there mentions a
slash command that doesn't exist.
"""

# Morgan's words (2026-11-16), like the description below
TITLE = "🎬 Welcome to the show, I'll be your VJ."

# Morgan's words, word for word
DESCRIPTION = (
    "I'm this server's bot, use me to play music and do dope stuff. "
    "All you gotta do is: type `/` in any chat and pick a command."
)
# Added under the description when /help is run in DMs, where the server-only commands won't work
IN_DMS = "🎞️ You're in my DMs, comrade: most of this only works in the server, so head back there to try it."

# Morgan's last line, with /listcommands (retired 2026-11-16) swapped for the dropdown that replaced it
LAST_LINE = "Tap a command to use it. For the rest of the commands: pick a topic below."

EVERYTHING_TITLE = "📜 Every command"

# The dropdown under every page
PICK_TOPIC = "Pick a topic: every command, by area"
TOUR_OPTION = "🎬 The tour"
EVERYTHING_OPTION = "📜 Every command"
