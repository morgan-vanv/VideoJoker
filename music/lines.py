"""Every user-facing line the music player says, in one place. Plain on purpose (Morgan, 2026-11-17): short, clear
lines with an emoji, like the Minecraft, event alert and raffle text.

`say` picks at random when a line is a list of options (none are right now) and fills in the {blanks}.
"""

import random

NOW_SHOWING = "🎵 Now playing"
UP_NEXT = "🎶 Up next"
INTERMISSION = "⏸️ Paused"

QUEUED = "🎶 Added to the queue: **{title}** (position {position})"
QUEUED_NEXT = "🎶 **{title}** plays next."
QUEUED_MANY = "🎶 Added {count} songs from **{title}** to the queue."

SKIPPED = "⏭️ Skipped."
STOPPED = "⏹️ Stopped, and the queue is cleared."
NOTHING_PLAYING = "Nothing is playing. Start something with `/play`."
QUEUE_EMPTY = "The queue is empty. Add something with `/play`."
QUEUE_CLEARED = "🧹 Cleared {count} songs from the queue."
REMOVED = "🗑️ Removed **{title}** from the queue."
BAD_POSITION = "There's no song at position {position}. Check `/queue`."
VOLUME_SET = "🔊 Volume: {volume}%"
VOLUME_SHOW = "🔊 Volume is at {volume}%."

LEFT = "👋 Left the voice channel and cleared the queue."
IDLE_LEFT = "👋 Nothing left to play, so I've left the voice channel."
RESTARTING = "🔄 The bot is restarting. Give it a minute, then `/play` again."
NOT_IN_VOICE = "Join a voice channel first, then try again."
NOT_CONNECTED = "I'm not in a voice channel. Use `/play` first."
WRONG_CHANNEL = "I'm playing music in **{channel}**. Join that channel to use the controls."

SEARCHING = "🔎 Searching for **{query}**..."
NOT_FOUND = "Couldn't find anything for **{query}**."
LOAD_FAILED = "Couldn't play **{title}**, so I skipped it."
TIDAL_NOT_CONFIGURED = "🎵 Tidal links aren't switched on here yet. YouTube, SoundCloud and Spotify links work."
LINK_FAILED = "{service} wouldn't share that link. Check it (private playlists stay private)."


def say(line: str | list[str], **kwargs) -> str:
    """Picks a line (random if given a list) and fills in the blanks."""
    if isinstance(line, list):
        line = random.choice(line)
    return line.format(**kwargs)
