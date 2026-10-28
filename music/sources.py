"""Turns what a user typed into Track objects.

Two jobs, kept separate on purpose:
- fetch_tracks(): fast. A link or search becomes one or many Tracks with just titles (playlists are read "flat").
- resolve_stream(): slow, done per track right before it plays. Gets the actual audio URL for ffmpeg.

YouTube and SoundCloud (and ~1,000 other sites) go through yt-dlp. Spotify's API doesn't stream audio, so a
Spotify link becomes "Artist - Title" search queries that YouTube answers. That's how every music bot does it.
"""
import asyncio
import base64
import functools
import logging
import os
import re
import time
from urllib.parse import urlparse

import aiohttp
import yt_dlp

from music.queue import Track

STREAM_URL_TTL = 60 * 60  # yt-dlp stream URLs expire after a few hours; refresh anything older than this

SPOTIFY_LINK = re.compile(r"open\.spotify\.com/(?:intl-\w+/)?(track|album|playlist)/([A-Za-z0-9]+)")
SPOTIFY_URI = re.compile(r"spotify:(track|album|playlist):([A-Za-z0-9]+)")


class TrackNotFound(Exception):
    """Nothing matched the link or search."""


class SpotifyNotConfigured(Exception):
    """A Spotify link was given but there are no API credentials in .env."""


def _ytdl_options() -> dict:
    """Builds yt-dlp options. Optional env vars let Morgan's YouTube Premium / SoundCloud Go+ accounts help."""
    options = {
        "format": "bestaudio/best",
        "noplaylist": True,                 # a watch?v=...&list=... link plays the video, not the whole list
        "extract_flat": "in_playlist",      # playlists: just titles+urls, no per-video work (that's resolve_stream's job)
        "default_search": "ytsearch1",      # plain text = YouTube search, first hit
        "quiet": True,
        "no_warnings": True,
        "logger": logging.getLogger("yt_dlp"),  # yt-dlp's own messages go to bot.log instead of raw stderr
        "skip_download": True,
        "source_address": "0.0.0.0",        # IPv4; some hosts stall over IPv6
    }
    cookies = os.getenv("YTDLP_COOKIES_FILE")
    if cookies:
        # Logged-in cookies (a YouTube Premium account works great) avoid the "sign in to confirm you're not a bot" wall
        options["cookiefile"] = cookies
    soundcloud_token = os.getenv("SOUNDCLOUD_OAUTH_TOKEN")
    if soundcloud_token:
        # yt-dlp's SoundCloud extractor accepts an OAuth token as "username oauth / password <token>"
        options["username"] = "oauth"
        options["password"] = soundcloud_token
    return options


async def _extract(query: str, **overrides) -> dict:
    """Runs yt-dlp in a worker thread. yt-dlp is blocking code; if we called it directly the whole bot would
    freeze (no buttons, no commands, audio stutter) for the seconds it takes."""
    options = {**_ytdl_options(), **overrides}
    loop = asyncio.get_running_loop()
    with yt_dlp.YoutubeDL(options) as ytdl:
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
    track.stream_url = info.get("url")
    track.resolved_at = time.monotonic()
    if info.get("duration"):
        track.duration = int(info["duration"])
    if info.get("title"):
        track.title = info["title"]
    track.thumbnail = track.thumbnail or info.get("thumbnail")


async def fetch_tracks(query: str, requester_id: int, requester_name: str) -> tuple[list[Track], str | None]:
    """Returns (tracks, playlist_title). playlist_title is None for a single track."""
    spotify_match = SPOTIFY_LINK.search(query) or SPOTIFY_URI.search(query)
    if spotify_match:
        kind, spotify_id = spotify_match.groups()
        return await SpotifyClient.shared().fetch(kind, spotify_id, requester_id, requester_name)

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
    """Makes sure `track.stream_url` is fresh. Called by the player right before playback."""
    if track.stream_url and track.resolved_at and time.monotonic() - track.resolved_at < STREAM_URL_TTL:
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
    if not track.stream_url:
        raise TrackNotFound(query)
    return track


class SpotifyClient:
    """Tiny Spotify Web API client (client-credentials flow). No library needed; it's three HTTP calls.

    Spotify never gives us audio. We read the track list and search YouTube for each "Artist - Title".
    Note: since late 2024, new Spotify dev apps can't read Spotify's own editorial playlists (they 404);
    user-made playlists, albums and tracks are fine.
    """
    _instance: "SpotifyClient | None" = None
    API = "https://api.spotify.com/v1"

    def __init__(self):
        self.client_id = os.getenv("SPOTIFY_CLIENT_ID")
        self.client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
        self._token: str | None = None
        self._token_expires = 0.0

    @classmethod
    def shared(cls) -> "SpotifyClient":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def _get_token(self, session: aiohttp.ClientSession) -> str:
        if self._token and time.monotonic() < self._token_expires:
            return self._token
        if not self.client_id or not self.client_secret:
            raise SpotifyNotConfigured()
        auth = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        async with session.post(
            "https://accounts.spotify.com/api/token",
            headers={"Authorization": f"Basic {auth}"},
            data={"grant_type": "client_credentials"},
        ) as response:
            response.raise_for_status()
            payload = await response.json()
        self._token = payload["access_token"]
        self._token_expires = time.monotonic() + payload.get("expires_in", 3600) - 60
        return self._token

    async def _get(self, session: aiohttp.ClientSession, path: str, **params) -> dict:
        token = await self._get_token(session)
        async with session.get(f"{self.API}{path}", headers={"Authorization": f"Bearer {token}"},
                               params=params) as response:
            response.raise_for_status()
            return await response.json()

    async def fetch(self, kind: str, spotify_id: str, requester_id: int,
                    requester_name: str) -> tuple[list[Track], str | None]:
        """Returns (tracks, collection_title). kind is 'track', 'album' or 'playlist'."""
        async with aiohttp.ClientSession() as session:
            if kind == "track":
                item = await self._get(session, f"/tracks/{spotify_id}")
                return [self._track(item, requester_id, requester_name)], None

            collection = await self._get(session, f"/{kind}s/{spotify_id}", fields="name,images")
            items: list[dict] = []
            page = await self._get(session, f"/{kind}s/{spotify_id}/tracks", limit=100 if kind == "playlist" else 50)
            while True:
                items.extend(page.get("items", []))
                if not page.get("next"):
                    break
                token = await self._get_token(session)
                async with session.get(page["next"], headers={"Authorization": f"Bearer {token}"}) as response:
                    response.raise_for_status()
                    page = await response.json()

        tracks = []
        for item in items:
            # playlist items wrap the track in {"track": {...}}; album items are the track itself
            data = item.get("track") if kind == "playlist" else item
            if data and data.get("name"):
                tracks.append(self._track(data, requester_id, requester_name))
        if not tracks:
            raise TrackNotFound(spotify_id)
        return tracks, collection.get("name") or kind

    @staticmethod
    def _track(data: dict, requester_id: int, requester_name: str) -> Track:
        artists = ", ".join(artist["name"] for artist in data.get("artists", []) if artist.get("name"))
        images = (data.get("album") or {}).get("images") or []
        duration_ms = data.get("duration_ms")
        return Track(
            title=data["name"],
            search_query=f"{artists} - {data['name']}" if artists else data["name"],
            duration=duration_ms // 1000 if duration_ms else None,
            artist=artists or None,
            thumbnail=images[0]["url"] if images else None,
            source="spotify",
            requester_id=requester_id,
            requester_name=requester_name,
        )


logging.getLogger("yt_dlp").setLevel(logging.WARNING)
