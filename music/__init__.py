"""The VideoJoker music player.

Layout (mirrors games/<name>/ — logic separate from Discord):
- queue.py   pure Python: Track dataclass, Queue with loop modes. No discord imports, easy to test.
- sources.py turns a link or search text into Tracks (yt-dlp for YouTube/SoundCloud, Spotify Web API for Spotify links).
- player.py  one GuildPlayer per server: owns the voice connection and the play loop.
- ui.py      the now-playing embed and its buttons, the queue embed.
- lines.py   the VJ's narration — every bit of user-facing copy lives here.
"""
