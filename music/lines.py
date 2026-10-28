"""The VJ's narration. Every user-facing line the music player says lives here, so the voice stays in one place.

Lists get a random pick (see `say`); single strings are used as-is.
"""
import random

NOW_SHOWING = "🎬 NOW SHOWING"
UP_NEXT = "📼 UP NEXT"
INTERMISSION = "⏸ INTERMISSION"

QUEUED = [
    "📼 The VJ loads the reel: **{title}**",
    "📼 Added to tonight's programme: **{title}**",
    "📼 **{title}** — the VJ has it on the shelf. Position {position}.",
]
QUEUED_NEXT = "📼 The VJ cuts in line for you: **{title}** plays next."
QUEUED_MANY = "📼 The VJ wheels in {count} tapes from **{title}**. This will be a long night, comrades."

SKIPPED = [
    "⏭ The VJ fast-forwards. Nobody wanted to see that part anyway.",
    "⏭ Skipped. The VJ has seen this one already.",
    "⏭ The tape jumps ahead. Action is coming.",
]
STOPPED = "🛑 The VJ ejects the tape. Movie over, comrades."
PAUSED = "⏸ Intermission! Go buy popcorn."
RESUMED = "▶️ The projector whirs back to life."
ALREADY_PAUSED = "The film is already paused, comrade."
NOT_PAUSED = "Nothing is paused. The film is rolling."
NOTHING_PLAYING = "Nothing is playing. Load a tape with `/play`."
QUEUE_EMPTY = "The reel has run out. Queue something with `/play`, comrade."
QUEUE_CLEARED = "🧹 The VJ sweeps {count} tapes off the shelf."
SHUFFLED = "🔀 The VJ throws the tapes in the air. New order!"
REMOVED = "🗑️ **{title}** is off the programme."
BAD_POSITION = "There is no tape at position {position}, comrade. Check `/queue`."
LOOP_SET = {
    "off": "🔁 Loop off. Every film plays once, as nature intended.",
    "track": "🔂 Looping this one film forever. Bold choice.",
    "queue": "🔁 Looping the whole programme. The cinema never closes.",
}
VOLUME_SET = "🔊 Volume: {volume}%"
VOLUME_SHOW = "🔊 Volume is at {volume}%."

JOINED = "🎥 The VJ sets up the projector in **{channel}**."
LEFT = "👋 The VJ packs up the projector. Goodnight, comrades."
IDLE_LEFT = "The cinema has emptied. The VJ packs up the projector."
ALREADY_HERE = "The VJ is already in **{channel}**."
NOT_IN_VOICE = "You are not in a voice channel. The VJ cannot narrate to an empty room."
NOT_CONNECTED = "The VJ isn't in a voice channel. Use `/play` or `/join` first."
WRONG_CHANNEL = "The VJ is showing a film in **{channel}**. Join the audience there to use the controls."

SEARCHING = "🔎 The VJ rummages through the tapes for **{query}**..."
NOT_FOUND = "The VJ searched every shelf and found nothing for **{query}**."
LOAD_FAILED = "The tape for **{title}** is damaged. The VJ skips it and moves on."
SPOTIFY_NOT_CONFIGURED = (
    "Spotify links need `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET` in `.env`. "
    "See SETUP_GUIDE.md — it's free."
)
SPOTIFY_FAILED = "Spotify wouldn't hand over that one. Check the link, comrade."


def say(line: str | list[str], **kwargs) -> str:
    """Picks a line (random if given a list) and fills in the blanks."""
    if isinstance(line, list):
        line = random.choice(line)
    return line.format(**kwargs)
