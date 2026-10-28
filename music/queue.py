"""Pure-Python queue logic for the music player. No Discord here, so it can be tested in isolation."""
import random
from collections import deque
from dataclasses import dataclass, field
from enum import Enum


class LoopMode(Enum):
    """What happens when a track finishes."""
    OFF = "off"      # play the next track, drop the finished one into history
    TRACK = "track"  # play the same track again
    QUEUE = "queue"  # put the finished track at the back of the line


@dataclass
class Track:  # pylint: disable=too-many-instance-attributes
    """One song, as the queue knows it.

    A Track is created cheaply (just title/url) and its `stream_url` is only resolved right before it plays.
    Why: stream URLs from yt-dlp expire after a few hours, and resolving a 100-song playlist up front
    would take ages. Spotify tracks don't even have a `url` to begin with, only a `search_query` we send to YouTube.
    """
    title: str
    url: str | None = None               # the page we can link people to (YouTube watch page, SoundCloud page)
    search_query: str | None = None      # used instead of `url` for Spotify tracks ("Artist - Title")
    stream_url: str | None = None        # the actual audio URL ffmpeg reads; filled in by sources.resolve_stream
    resolved_at: float | None = None     # time.monotonic() when stream_url was fetched; they go stale
    duration: int | None = None          # seconds, if known
    artist: str | None = None            # uploader / channel / Spotify artist
    thumbnail: str | None = None
    source: str = "youtube"              # "youtube", "soundcloud", "spotify" — decides the embed's badge
    requester_id: int = 0
    requester_name: str = ""

    @property
    def pretty_duration(self) -> str:
        """`3:07`, or `1:02:15` for anything over an hour, or `live` when unknown."""
        if self.duration is None:
            return "live"
        minutes, seconds = divmod(int(self.duration), 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"


@dataclass
class Queue:
    """Upcoming tracks, the one playing now, and the ones already played."""
    upcoming: deque = field(default_factory=deque)
    current: Track | None = None
    history: deque = field(default_factory=lambda: deque(maxlen=50))
    loop: LoopMode = LoopMode.OFF

    def add(self, track: Track, play_next: bool = False) -> int:
        """Adds a track and returns its 1-based position in the upcoming list."""
        if play_next:
            self.upcoming.appendleft(track)
            return 1
        self.upcoming.append(track)
        return len(self.upcoming)

    def add_many(self, tracks: list[Track], play_next: bool = False) -> None:
        """Adds a whole playlist. With play_next the playlist keeps its order at the front."""
        if play_next:
            self.upcoming.extendleft(reversed(tracks))
        else:
            self.upcoming.extend(tracks)

    def advance(self) -> Track | None:
        """Moves to the next track according to the loop mode. Returns it, or None when the queue is empty."""
        finished = self.current
        if finished is not None:
            if self.loop == LoopMode.TRACK:
                return finished  # same track again; current is unchanged
            self.history.append(finished)
            if self.loop == LoopMode.QUEUE:
                self.upcoming.append(finished)

        self.current = self.upcoming.popleft() if self.upcoming else None
        return self.current

    def skip(self) -> Track | None:
        """Like advance(), but a skip always moves on even when looping one track."""
        if self.current is not None and self.loop == LoopMode.TRACK:
            self.history.append(self.current)
            self.current = None
        return self.advance()

    def remove(self, position: int) -> Track | None:
        """Removes the track at a 1-based position. Returns it, or None if the position is out of range."""
        if 1 <= position <= len(self.upcoming):
            track = self.upcoming[position - 1]
            del self.upcoming[position - 1]
            return track
        return None

    def shuffle(self) -> None:
        """Shuffles only what's upcoming; the current track keeps playing."""
        tracks = list(self.upcoming)
        random.shuffle(tracks)
        self.upcoming = deque(tracks)

    def clear(self) -> int:
        """Empties the upcoming list and returns how many tracks were dropped."""
        dropped = len(self.upcoming)
        self.upcoming.clear()
        return dropped

    @property
    def total_duration(self) -> int:
        """Seconds of known-length music still upcoming (live streams count as 0)."""
        return sum(track.duration or 0 for track in self.upcoming)

    def __len__(self) -> int:
        return len(self.upcoming)
