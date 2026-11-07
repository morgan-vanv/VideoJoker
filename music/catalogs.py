"""Spotify and Tidal links: services that tell us what's on a track, album or playlist, but never give us audio.

Both are DRM-protected, so no bot can play them directly. Instead we read the track list ("Artist - Title") and
YouTube plays each song (sources.resolve_stream searches for it right before it plays). That's how every music
bot does it.

- Spotify: the official Web API (SPOTIFY_CLIENT_ID/SECRET) for tracks and albums. Since February 2026 that API
  won't list other people's playlists, so playlists, and everything when the API isn't set up or refuses, come
  from Spotify's public embed page (the little player websites put on their pages). The embed page isn't an
  official API: if Spotify changes it, this part breaks until we update parse_spotify_embed().
- Tidal: the official TIDAL API (TIDAL_CLIENT_ID/SECRET, a free developer account), for all three.
"""

import base64
import json
import logging
import os
import re
import time

import aiohttp

from music.queue import Track

SPOTIFY_LINK = re.compile(r"open\.spotify\.com/(?:intl-[\w-]+/)?(?:embed/)?(track|album|playlist)/([A-Za-z0-9]+)")
SPOTIFY_URI = re.compile(r"spotify:(track|album|playlist):([A-Za-z0-9]+)")
# tidal.com/track/1, tidal.com/browse/album/2, listen.tidal.com/playlist/<uuid>, ...
TIDAL_LINK = re.compile(r"tidal\.com/(?:browse/)?(track|album|playlist)/([A-Za-z0-9-]+)")

MAX_TRACKS = 500  # a link with more than this queues the first 500 (and the VJ isn't playing 500 songs anyway)
USER_AGENT = "VideoJoker/1.0 (Discord music bot; +https://github.com/morgan-vanv/VideoJoker)"
TIMEOUT = aiohttp.ClientTimeout(total=20)


class LinkNotReadable(Exception):
    """The service wouldn't give us that link's track list. `service` is its name, for the VJ's reply."""

    def __init__(self, service: str, reason: str):
        super().__init__(f"{service}: {reason}")
        self.service = service


class TidalNotConfigured(Exception):
    """A Tidal link was given but TIDAL_CLIENT_ID/SECRET aren't in .env."""


def _track(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    title: str, artists: str, duration: int | None, thumbnail: str | None, source: str, requester: tuple[int, str]
) -> Track:
    return Track(
        title=title,
        search_query=f"{artists} - {title}" if artists else title,
        duration=duration,
        artist=artists or None,
        thumbnail=thumbnail,
        source=source,
        requester_id=requester[0],
        requester_name=requester[1],
    )


class _ClientCredentials:  # pylint: disable=too-few-public-methods
    """The OAuth "client credentials" login both services use: trade our app's id + secret for a token that's
    good for about an hour, and reuse it until then."""

    def __init__(self, token_url: str, id_variable: str, secret_variable: str):
        self.token_url = token_url
        self.client_id = os.getenv(id_variable)
        self.client_secret = os.getenv(secret_variable)
        self._token: str | None = None
        self._expires = 0.0

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    async def token(self, session: aiohttp.ClientSession) -> str:
        if self._token and time.monotonic() < self._expires:
            return self._token
        auth = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        async with session.post(
            self.token_url, headers={"Authorization": f"Basic {auth}"}, data={"grant_type": "client_credentials"}
        ) as response:
            response.raise_for_status()
            payload = await response.json()
        self._token = payload["access_token"]
        self._expires = time.monotonic() + payload.get("expires_in", 3600) - 60
        return self._token


# ---------------------------------------------------------------- Spotify


class SpotifyClient:
    """Spotify links → Tracks. The official API when it's set up and allowed, otherwise the embed page."""

    _instance: "SpotifyClient | None" = None
    API = "https://api.spotify.com/v1"
    EMBED = "https://open.spotify.com/embed"

    def __init__(self):
        self.login = _ClientCredentials(
            "https://accounts.spotify.com/api/token", "SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET"
        )

    @classmethod
    def shared(cls) -> "SpotifyClient":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def fetch(self, kind: str, spotify_id: str, requester: tuple[int, str]) -> tuple[list[Track], str | None]:
        """Returns (tracks, collection_title). kind is 'track', 'album' or 'playlist'."""
        async with aiohttp.ClientSession(timeout=TIMEOUT, headers={"User-Agent": USER_AGENT}) as session:
            if kind != "playlist" and self.login.configured:
                try:
                    return await self._from_api(session, kind, spotify_id, requester)
                except aiohttp.ClientError as error:
                    logging.warning("Spotify API refused the %s (%s); trying the embed page", kind, error)
            return await self._from_embed(session, kind, spotify_id, requester)

    async def _get(self, session: aiohttp.ClientSession, url: str, **params) -> dict:
        token = await self.login.token(session)
        async with session.get(url, headers={"Authorization": f"Bearer {token}"}, params=params) as response:
            response.raise_for_status()
            return await response.json()

    async def _from_api(
        self, session: aiohttp.ClientSession, kind: str, spotify_id: str, requester: tuple[int, str]
    ) -> tuple[list[Track], str | None]:
        if kind == "track":
            return [self._api_track(await self._get(session, f"{self.API}/tracks/{spotify_id}"), requester)], None
        album = await self._get(session, f"{self.API}/albums/{spotify_id}")
        items = list(album.get("tracks", {}).get("items", []))
        next_page = album.get("tracks", {}).get("next")
        while next_page and len(items) < MAX_TRACKS:  # albums over 50 songs come in pages
            page = await self._get(session, next_page)
            items.extend(page.get("items", []))
            next_page = page.get("next")
        for item in items:  # album songs don't carry the cover themselves
            item.setdefault("album", {"images": album.get("images", [])})
        tracks = [self._api_track(item, requester) for item in items[:MAX_TRACKS] if item.get("name")]
        return tracks, album.get("name") or "album"

    @staticmethod
    def _api_track(data: dict, requester: tuple[int, str]) -> Track:
        artists = ", ".join(artist["name"] for artist in data.get("artists", []) if artist.get("name"))
        images = (data.get("album") or {}).get("images") or []
        duration_ms = data.get("duration_ms")
        return _track(
            data["name"],
            artists,
            duration_ms // 1000 if duration_ms else None,
            images[0]["url"] if images else None,
            "spotify",
            requester,
        )

    async def _from_embed(
        self, session: aiohttp.ClientSession, kind: str, spotify_id: str, requester: tuple[int, str]
    ) -> tuple[list[Track], str | None]:
        try:
            async with session.get(f"{self.EMBED}/{kind}/{spotify_id}") as response:
                response.raise_for_status()
                html = await response.text()
        except aiohttp.ClientError as error:
            raise LinkNotReadable("Spotify", f"embed page: {error}") from error
        name, songs, cover = parse_spotify_embed(html)
        tracks = [_track(title, artists, duration, cover, "spotify", requester) for title, artists, duration in songs]
        return tracks[:MAX_TRACKS], (name or kind) if kind != "track" else None


_EMBED_SCRIPT = re.compile(r'<script[^>]*\bid="(__NEXT_DATA__|initial-state|resource)"[^>]*>(.*?)</script>', re.S)


def parse_spotify_embed(html: str) -> tuple[str | None, list[tuple[str, str, int | None]], str | None]:
    """Reads the track list out of a Spotify embed page: (name, [(title, artists, seconds)], cover image).

    The page is a small web app; the data it shows is in a <script> tag as JSON. Spotify has used three
    versions of that tag over the years (plain JSON in __NEXT_DATA__, or base64 in "initial-state" or
    "resource"), so we look for all three, the same way the spotify-url-info library does.
    """
    entity = None
    for script_id, body in _EMBED_SCRIPT.findall(html):
        try:
            if script_id == "__NEXT_DATA__":
                entity = json.loads(body)["props"]["pageProps"]["state"]["data"]["entity"]
            elif script_id == "initial-state":
                entity = json.loads(base64.b64decode(body))["data"]["entity"]
            else:
                entity = json.loads(base64.b64decode(body))
        except ValueError, KeyError, TypeError:
            continue
        if isinstance(entity, dict) and entity.get("type"):
            break
        entity = None
    if entity is None:
        raise LinkNotReadable("Spotify", "no track data on the embed page (has Spotify changed it?)")

    sources = (entity.get("coverArt") or {}).get("sources") or []
    cover = max(sources, key=lambda image: image.get("width") or 0)["url"] if sources else None

    def seconds(milliseconds) -> int | None:
        return int(milliseconds) // 1000 if milliseconds else None

    if "trackList" in entity:  # album or playlist
        songs = [
            # subtitle is the artists, with non-breaking spaces after the commas
            (item["title"], (item.get("subtitle") or "").replace(" ", " "), seconds(item.get("duration")))
            for item in entity["trackList"]
            if item.get("title")
        ]
    else:  # a single track
        artists = ", ".join(artist["name"] for artist in entity.get("artists", []) if artist.get("name"))
        title = entity.get("title") or entity.get("name")
        songs = [(title, artists, seconds(entity.get("duration")))] if title else []
    return entity.get("name"), songs, cover


# ---------------------------------------------------------------- Tidal


class TidalClient:
    """Tidal links → Tracks, through the official TIDAL API (https://developer.tidal.com).

    Its answers follow the JSON:API format: each thing has an "id", a "type" and "attributes" (title, ...),
    and links to other things ("relationships") are just ids. Asking with include=artists adds the linked
    artists to an "included" list next to the answer, so one request gives songs plus their artist names.
    """

    _instance: "TidalClient | None" = None
    API = "https://openapi.tidal.com/v2"
    BATCH = 20  # the API's limit for "these tracks, please"

    def __init__(self):
        self.login = _ClientCredentials(
            "https://auth.tidal.com/v1/oauth2/token", "TIDAL_CLIENT_ID", "TIDAL_CLIENT_SECRET"
        )
        # Tidal's catalogue differs a little per country, so every request says which one. Default: US.
        self.country = os.getenv("TIDAL_COUNTRY_CODE") or "US"

    @classmethod
    def shared(cls) -> "TidalClient":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def fetch(self, kind: str, tidal_id: str, requester: tuple[int, str]) -> tuple[list[Track], str | None]:
        """Returns (tracks, collection_title). kind is 'track', 'album' or 'playlist'."""
        if not self.login.configured:
            raise TidalNotConfigured()
        try:
            async with aiohttp.ClientSession(timeout=TIMEOUT, headers={"User-Agent": USER_AGENT}) as session:
                if kind == "track":
                    return await self._tracks(session, [tidal_id], requester), None
                collection = await self._get(session, f"/{kind}s/{tidal_id}")
                attributes = collection.get("data", {}).get("attributes", {})
                track_ids = await self._item_ids(session, f"/{kind}s/{tidal_id}/relationships/items")
                title = attributes.get("title") or attributes.get("name") or kind  # albums: title, playlists: name
                return await self._tracks(session, track_ids, requester), title
        except aiohttp.ClientError as error:
            raise LinkNotReadable("Tidal", str(error)) from error

    async def _get(self, session: aiohttp.ClientSession, path: str, params: list | None = None) -> dict:
        token = await self.login.token(session)
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.api+json"}
        query = [("countryCode", self.country), *(params or [])]
        async with session.get(f"{self.API}{path}", headers=headers, params=query) as response:
            response.raise_for_status()
            return await response.json(content_type=None)

    async def _item_ids(self, session: aiohttp.ClientSession, path: str) -> list[str]:
        """The track ids in an album or playlist, page by page (videos are skipped: there's nothing to search)."""
        ids: list[str] = []
        params: list = []
        while len(ids) < MAX_TRACKS:
            page = await self._get(session, path, params)
            ids.extend(item["id"] for item in page.get("data", []) if item.get("type") == "tracks")
            next_link = (page.get("links") or {}).get("next")
            cursor = re.search(r"page\[cursor\]=([^&]+)", next_link or "")
            if not cursor:
                break
            params = [("page[cursor]", cursor.group(1))]
        return ids[:MAX_TRACKS]

    async def _tracks(self, session: aiohttp.ClientSession, track_ids: list[str], requester) -> list[Track]:
        tracks: list[Track] = []
        for start in range(0, len(track_ids), self.BATCH):
            batch = track_ids[start : start + self.BATCH]
            params = [("include", "artists"), *(("filter[id]", track_id) for track_id in batch)]
            tracks.extend(tidal_tracks(await self._get(session, "/tracks", params), batch, requester))
        return tracks


_ISO_DURATION = re.compile(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?")


def iso_duration_seconds(text: str | None) -> int | None:
    """Tidal writes durations the ISO 8601 way: "PT3M27S" is 3 minutes 27 seconds."""
    match = _ISO_DURATION.fullmatch(text or "")
    if not match or not any(match.groups()):
        return None
    hours, minutes, seconds = (float(part) if part else 0 for part in match.groups())
    return int(hours * 3600 + minutes * 60 + seconds)


def tidal_tracks(document: dict, order: list[str], requester: tuple[int, str]) -> list[Track]:
    """Turns a TIDAL API answer about tracks (with include=artists) into Tracks, in the order of `order`."""
    artist_names = {
        item["id"]: item.get("attributes", {}).get("name")
        for item in document.get("included", [])
        if item.get("type") == "artists"
    }
    data = document.get("data", [])
    by_id = {item["id"]: item for item in (data if isinstance(data, list) else [data])}
    tracks = []
    for track_id in order:
        item = by_id.get(track_id)
        if not item or not item.get("attributes", {}).get("title"):
            continue  # not available in this country, or removed
        attributes = item["attributes"]
        artist_ids = [link["id"] for link in item.get("relationships", {}).get("artists", {}).get("data", [])]
        artists = ", ".join(name for name in (artist_names.get(artist_id) for artist_id in artist_ids) if name)
        tracks.append(
            _track(
                attributes["title"], artists, iso_duration_seconds(attributes.get("duration")), None, "tidal", requester
            )
        )
    return tracks


def log_settings() -> None:
    """Startup log for the two services (called from sources.log_optional_settings)."""
    if not (os.getenv("SPOTIFY_CLIENT_ID") and os.getenv("SPOTIFY_CLIENT_SECRET")):
        logging.info("SPOTIFY_CLIENT_ID/SECRET not set: Spotify links are read from Spotify's public embed pages only.")
    if not (os.getenv("TIDAL_CLIENT_ID") and os.getenv("TIDAL_CLIENT_SECRET")):
        logging.warning(
            "TIDAL_CLIENT_ID/SECRET not set: Tidal links are off (YouTube, SoundCloud, Spotify still work)."
        )
