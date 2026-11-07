"""Turns what a user typed into Track objects.

Two jobs, kept separate on purpose:
- fetch_tracks(): fast. A link or search becomes one or many Tracks with just titles (playlists are read "flat").
- resolve_stream(): slow, done per track right before it plays. Gets the actual audio URL for ffmpeg.

YouTube and SoundCloud (and ~1,000 other sites) go through yt-dlp. Spotify and Tidal never give out audio, so
their links become "Artist - Title" search queries that YouTube answers (music/catalogs.py).
"""

import asyncio
import contextlib
import functools
import logging
import os
import re
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse

import yt_dlp

from music import catalogs
from music.queue import Track

STREAM_URL_TTL = 60 * 60  # yt-dlp stream URLs expire after a few hours; refresh anything older than this

# In production the container's files are read-only, except /app/data and /tmp (CLAUDE.md, "Production
# hosting"). yt-dlp caches YouTube's player code in ~/.cache by default, which is read-only there, so the
# cache goes in /tmp. It's only a cache: a restart empties it and the first /play after is a bit slower.
YTDLP_CACHE_DIR = Path(tempfile.gettempdir()) / "videojoker-yt-dlp"
# Same idea for Deno, which runs YouTube's JavaScript puzzles for yt-dlp (see requirements.txt). It keeps a
# cache in DENO_DIR (default ~/.cache/deno) even when told not to. yt-dlp passes our environment on to Deno.
# setdefault: if someone already set DENO_DIR themselves, theirs wins.
os.environ.setdefault("DENO_DIR", str(Path(tempfile.gettempdir()) / "videojoker-deno"))

# yt-dlp rewrites the cookies file from scratch every time it finishes (YouTube keeps rotating them). Two
# lookups at once (two servers, or a /play while the next song loads) could read a half-written file, or
# save a half-read one over the good one, and the logged-in cookies would be gone. So when there's a cookies
# file, lookups take turns. Each one takes a second or two, so nobody will notice the wait.
_cookies_lock = asyncio.Lock()


class TrackNotFound(Exception):
    """Nothing matched the link or search."""


class _BlankOutLinks(logging.Filter):  # pylint: disable=too-few-public-methods  # a logging filter needs only filter()
    """yt-dlp's warnings can mention links, and stream links carry the server's IP and signatures: blank them."""

    _LINK = re.compile(r"https?://\S+")

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = self._LINK.sub("<link>", record.getMessage())
        record.args = ()
        return True


_YTDLP_LOGGER = logging.getLogger("yt_dlp")
_YTDLP_LOGGER.addFilter(_BlankOutLinks())


def _ytdl_options() -> dict:
    """Builds yt-dlp options. Optional env vars let Morgan's YouTube Premium / SoundCloud Go+ accounts help."""
    options = {
        "format": "bestaudio/best",
        "noplaylist": True,  # a watch?v=...&list=... link plays the video, not the whole list
        "extract_flat": "in_playlist",  # playlists: just titles+urls, no per-video work (that's resolve_stream's job)
        "default_search": "ytsearch1",  # plain text = YouTube search, first hit
        "quiet": True,
        "logger": _YTDLP_LOGGER,  # yt-dlp's own messages (warnings included) go to bot.log, links blanked out
        "skip_download": True,
        "source_address": "0.0.0.0",  # IPv4; some hosts stall over IPv6
        "cachedir": str(YTDLP_CACHE_DIR),
    }
    cookies = _cookies_file()
    if cookies:
        # Logged-in cookies (a YouTube Premium account works great) avoid the "sign in to confirm you're not a bot" wall
        options["cookiefile"] = cookies
    soundcloud_token = os.getenv("SOUNDCLOUD_OAUTH_TOKEN")
    if soundcloud_token:
        # yt-dlp's SoundCloud extractor accepts an OAuth token as "username oauth / password <token>"
        options["username"] = "oauth"
        options["password"] = soundcloud_token
    return options


def log_optional_settings() -> None:
    """Says at startup which optional music extras are on. A missing one only switches that extra off:
    the bot must always start, because the production host rolls back a release that doesn't."""
    catalogs.log_settings()  # Spotify and Tidal
    if os.getenv("YTDLP_COOKIES_FILE"):
        _cookies_file()  # checks the file now, so a problem shows up in the startup log, not at the first /play
    else:
        logging.info("YTDLP_COOKIES_FILE not set: YouTube without cookies (may hit the 'not a bot' wall).")
    if not os.getenv("SOUNDCLOUD_OAUTH_TOKEN"):
        logging.info("SOUNDCLOUD_OAUTH_TOKEN not set: SoundCloud plays in standard quality.")


def cookies_in_use() -> bool:
    """Whether yt-dlp is using the YouTube cookies file (for the once-per-song log line)."""
    return _cookies_file() is not None


@functools.cache  # checked once per run, so a problem is logged once instead of on every song
def _cookies_file() -> str | None:
    """The YouTube cookies file from .env, or None if it's missing or unusable.

    yt-dlp doesn't only read this file: when it's done, it writes the cookies back. So the file has to be
    somewhere writable, like data/ (that's /app/data in Docker). If it's somewhere read-only, every /play
    would crash at the moment yt-dlp saves. Playing without cookies (and saying why in the log) is better.
    """
    path = os.getenv("YTDLP_COOKIES_FILE")
    if not path:
        return None
    if not os.path.isfile(path):
        logging.warning("YTDLP_COOKIES_FILE=%s doesn't exist. Playing without YouTube cookies.", path)
        return None
    if not os.access(path, os.W_OK):
        logging.warning(
            "YTDLP_COOKIES_FILE=%s isn't writable, and yt-dlp saves cookies back. Keep it in data/. "
            "Playing without YouTube cookies.",
            path,
        )
        return None
    return path


async def _extract(query: str, **overrides) -> dict:
    """Runs yt-dlp in a worker thread. yt-dlp is blocking code; if we called it directly the whole bot would
    freeze (no buttons, no commands, audio stutter) for the seconds it takes."""
    options = {**_ytdl_options(), **overrides}
    loop = asyncio.get_running_loop()
    # nullcontext() is a "do nothing" stand-in, so without cookies nobody waits for anybody
    wait_our_turn = _cookies_lock if "cookiefile" in options else contextlib.nullcontext()
    async with wait_our_turn:
        with yt_dlp.YoutubeDL(options) as ytdl:  # leaving this block is when yt-dlp saves the cookies
            call = functools.partial(ytdl.extract_info, query, download=False)
            try:
                info = await loop.run_in_executor(None, call)
            except yt_dlp.utils.DownloadError as error:
                raise TrackNotFound(query) from error
    if info is None:
        raise TrackNotFound(query)
    return info


def _source_name(url: str | None) -> str:
    host = urlparse(url or "").hostname or ""
    if "soundcloud" in host:
        return "soundcloud"
    if "youtu" in host:
        return "youtube"
    return "other"


def _track_from_info(info: dict, requester_id: int, requester_name: str) -> Track:
    """Maps a yt-dlp info dict (flat or full) onto our Track."""
    page_url = info.get("webpage_url") or info.get("url")
    track = Track(
        title=info.get("title") or "Untitled",
        url=page_url,
        duration=int(info["duration"]) if info.get("duration") else None,
        artist=info.get("uploader") or info.get("channel") or info.get("artist"),
        thumbnail=info.get("thumbnail") or _first_thumbnail(info),
        source=_source_name(page_url),
        requester_id=requester_id,
        requester_name=requester_name,
    )
    # A full extraction (single video) already carries the audio URL. Flat playlist entries don't.
    if info.get("formats") or info.get("requested_formats"):
        _fill_stream(track, info)
    return track


def _first_thumbnail(info: dict) -> str | None:
    thumbnails = info.get("thumbnails") or []
    return thumbnails[-1].get("url") if thumbnails else None


def _fill_stream(track: Track, info: dict) -> None:
    # sanitize_info turns yt-dlp's answer into plain JSON-able data, so music/stream.py can hand it to the
    # yt-dlp that downloads the audio (--load-info-json). Only kept if yt-dlp found a playable format.
    track.stream_info = yt_dlp.YoutubeDL.sanitize_info(info) if info.get("url") else None
    track.resolved_at = time.monotonic()
    if info.get("duration"):
        track.duration = int(info["duration"])
    if info.get("title"):
        track.title = info["title"]
    track.thumbnail = track.thumbnail or info.get("thumbnail")


async def fetch_tracks(query: str, requester_id: int, requester_name: str) -> tuple[list[Track], str | None]:
    """Returns (tracks, playlist_title). playlist_title is None for a single track."""
    requester = (requester_id, requester_name)
    for pattern, client in (
        (catalogs.SPOTIFY_LINK, catalogs.SpotifyClient),
        (catalogs.SPOTIFY_URI, catalogs.SpotifyClient),
        (catalogs.TIDAL_LINK, catalogs.TidalClient),
    ):
        if match := pattern.search(query):
            kind, item_id = match.groups()
            tracks, title = await client.shared().fetch(kind, item_id, requester)
            if not tracks:
                raise TrackNotFound(query)
            return tracks, title

    info = await _extract(query)
    if "entries" in info:  # playlist, album, set, or a search (which yt-dlp also returns as a "playlist")
        entries = [entry for entry in info["entries"] if entry]
        if not entries:
            raise TrackNotFound(query)
        tracks = [_track_from_info(entry, requester_id, requester_name) for entry in entries]
        is_search = info.get("extractor", "").endswith("search")
        if is_search:
            return tracks[:1], None
        return tracks, info.get("title") or "playlist"
    return [_track_from_info(info, requester_id, requester_name)], None


async def resolve_stream(track: Track) -> Track:
    """Makes sure `track.stream_info` is fresh. Called by the player right before playback."""
    if track.stream_info and track.resolved_at and time.monotonic() - track.resolved_at < STREAM_URL_TTL:
        return track

    query = track.url or f"ytsearch1:{track.search_query}"
    info = await _extract(query, extract_flat=False)
    if "entries" in info:  # a search comes back as a one-item playlist
        entries = [entry for entry in info["entries"] if entry]
        if not entries:
            raise TrackNotFound(query)
        info = entries[0]
        track.url = track.url or info.get("webpage_url")
    _fill_stream(track, info)
    if not track.stream_info:
        raise TrackNotFound(query)
    return track


logging.getLogger("yt_dlp").setLevel(logging.WARNING)
