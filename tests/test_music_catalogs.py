"""Spotify and Tidal links (music/catalogs.py). No real Spotify or Tidal: the embed pages are made up in the
shape Spotify uses, and Tidal is a tiny local web server that answers like the TIDAL API's published spec."""

import base64
import json

import pytest
from aiohttp import web

from music import catalogs, sources

REQUESTER = (1, "Morgan")


# ---- link recognition


@pytest.mark.parametrize(
    ("text", "pattern", "expected"),
    [
        (
            "https://open.spotify.com/track/4uLU6hMCjMI75M1A2tKUQC?si=x",
            catalogs.SPOTIFY_LINK,
            ("track", "4uLU6hMCjMI75M1A2tKUQC"),
        ),
        (
            "https://open.spotify.com/intl-de/album/1DFixLWuPkv3KT3TnV35m3",
            catalogs.SPOTIFY_LINK,
            ("album", "1DFixLWuPkv3KT3TnV35m3"),
        ),
        ("spotify:playlist:37i9dQZF1DXcBWIGoYBM5M", catalogs.SPOTIFY_URI, ("playlist", "37i9dQZF1DXcBWIGoYBM5M")),
        ("https://tidal.com/browse/track/77646169/u", catalogs.TIDAL_LINK, ("track", "77646169")),
        ("https://listen.tidal.com/album/1550545", catalogs.TIDAL_LINK, ("album", "1550545")),
        (
            "https://tidal.com/playlist/36ea71a8-445e-41a4-82ab-6628c581535d",
            catalogs.TIDAL_LINK,
            ("playlist", "36ea71a8-445e-41a4-82ab-6628c581535d"),
        ),
    ],
)
def test_links_are_recognised(text, pattern, expected):
    assert pattern.search(text).groups() == expected


# ---- Spotify embed pages


def _next_data_page(entity: dict) -> str:
    data = json.dumps({"props": {"pageProps": {"state": {"data": {"entity": entity}}}}})
    return f'<html><body><script id="__NEXT_DATA__" type="application/json">{data}</script></body></html>'


def test_embed_playlist_gives_every_song_with_artists():
    page = _next_data_page(
        {
            "type": "playlist",
            "name": "Ugandan Bangers",
            "coverArt": {
                "sources": [
                    {"url": "https://i.scdn.co/small", "width": 64},
                    {"url": "https://i.scdn.co/big", "width": 640},
                ]
            },
            "trackList": [
                {"title": "Sitya Loss", "subtitle": "Eddy Kenzo", "duration": 215000},
                {"title": "Nakupenda", "subtitle": "Artist One, Artist Two", "duration": 180500},
            ],
        }
    )
    name, songs, cover = catalogs.parse_spotify_embed(page)
    assert name == "Ugandan Bangers"
    assert songs == [("Sitya Loss", "Eddy Kenzo", 215), ("Nakupenda", "Artist One, Artist Two", 180)]
    assert cover == "https://i.scdn.co/big"


def test_embed_single_track_in_base64_script():
    entity = {
        "type": "track",
        "name": "Immaterial",
        "title": "Immaterial",
        "duration": 232806,
        "artists": [{"name": "SOPHIE"}],
    }
    body = base64.b64encode(json.dumps({"data": {"entity": entity}}).encode()).decode()
    page = f'<html><body><script id="initial-state" type="text/plain">{body}</script></body></html>'
    name, songs, _ = catalogs.parse_spotify_embed(page)
    assert name == "Immaterial"
    assert songs == [("Immaterial", "SOPHIE", 232)]


def test_embed_page_without_data_says_so():
    with pytest.raises(catalogs.LinkNotReadable) as error:
        catalogs.parse_spotify_embed("<html><body>Spotify redesigned everything</body></html>")
    assert error.value.service == "Spotify"


# ---- Tidal


def test_iso_durations():
    assert catalogs.iso_duration_seconds("PT3M27S") == 207
    assert catalogs.iso_duration_seconds("PT1H2M3S") == 3723
    assert catalogs.iso_duration_seconds("PT45.5S") == 45
    assert catalogs.iso_duration_seconds(None) is None
    assert catalogs.iso_duration_seconds("garbage") is None


def _tidal_track(track_id: str, title: str, artist_ids: list[str]) -> dict:
    return {
        "id": track_id,
        "type": "tracks",
        "attributes": {"title": title, "duration": "PT3M0S", "isrc": "XX0000000000"},
        "relationships": {"artists": {"data": [{"id": a, "type": "artists"} for a in artist_ids]}},
    }


def test_tidal_tracks_keep_the_order_and_find_artist_names():
    document = {
        "data": [_tidal_track("2", "Second", ["a2"]), _tidal_track("1", "First", ["a1", "a2"])],
        "included": [
            {"id": "a1", "type": "artists", "attributes": {"name": "Alpha"}},
            {"id": "a2", "type": "artists", "attributes": {"name": "Beta"}},
        ],
    }
    tracks = catalogs.tidal_tracks(document, ["1", "2", "3"], REQUESTER)  # "3" isn't available: skipped
    assert [(t.title, t.artist, t.search_query, t.duration, t.source) for t in tracks] == [
        ("First", "Alpha, Beta", "Alpha, Beta - First", 180, "tidal"),
        ("Second", "Beta", "Beta - Second", 180, "tidal"),
    ]


@pytest.fixture(name="fake_tidal")
async def _fake_tidal():
    """A local stand-in for auth.tidal.com + openapi.tidal.com: a 3-song playlist (plus a video) in two pages."""
    seen = []

    async def token(request):
        assert request.headers["Authorization"].startswith("Basic ")
        return web.json_response({"access_token": "fake-token", "expires_in": 3600})

    async def playlist(request):
        seen.append(request.path_qs)
        return web.json_response({"data": {"id": "pl", "type": "playlists", "attributes": {"name": "Road trip"}}})

    async def items(request):
        seen.append(request.path_qs)
        if request.query.get("page[cursor]") == "two":
            return web.json_response({"data": [{"id": "3", "type": "tracks"}], "links": {"self": "/x"}})
        return web.json_response(
            {
                "data": [{"id": "1", "type": "tracks"}, {"id": "v9", "type": "videos"}, {"id": "2", "type": "tracks"}],
                "links": {"self": "/x", "next": "/playlists/pl/relationships/items?countryCode=US&page[cursor]=two"},
            }
        )

    async def tracks(request):
        seen.append(request.path_qs)
        assert request.headers["Authorization"] == "Bearer fake-token"
        assert request.query["countryCode"] == "US"
        ids = request.query.getall("filter[id]")
        return web.json_response(
            {
                "data": [_tidal_track(i, f"Song {i}", ["a"]) for i in ids],
                "included": [{"id": "a", "type": "artists", "attributes": {"name": "The Band"}}],
            }
        )

    app = web.Application()
    app.router.add_post("/v1/oauth2/token", token)
    app.router.add_get("/v2/playlists/pl", playlist)
    app.router.add_get("/v2/playlists/pl/relationships/items", items)
    app.router.add_get("/v2/tracks", tracks)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]  # pylint: disable=protected-access
    yield f"http://127.0.0.1:{port}", seen
    await runner.cleanup()


async def test_tidal_playlist_end_to_end(monkeypatch, fake_tidal):
    base, seen = fake_tidal
    monkeypatch.setenv("TIDAL_CLIENT_ID", "id")
    monkeypatch.setenv("TIDAL_CLIENT_SECRET", "secret")
    monkeypatch.delenv("TIDAL_COUNTRY_CODE", raising=False)
    client = catalogs.TidalClient()
    client.API = f"{base}/v2"
    client.login.token_url = f"{base}/v1/oauth2/token"
    monkeypatch.setattr(catalogs.TidalClient, "_instance", client)

    tracks, title = await sources.fetch_tracks("https://tidal.com/playlist/pl", *REQUESTER)
    assert title == "Road trip"
    assert [t.search_query for t in tracks] == ["The Band - Song 1", "The Band - Song 2", "The Band - Song 3"]
    assert any("page%5Bcursor%5D=two" in path or "page[cursor]=two" in path for path in seen)  # followed page 2


async def test_tidal_link_without_settings(monkeypatch):
    monkeypatch.delenv("TIDAL_CLIENT_ID", raising=False)
    monkeypatch.setattr(catalogs.TidalClient, "_instance", None)
    with pytest.raises(catalogs.TidalNotConfigured):
        await sources.fetch_tracks("https://tidal.com/track/1", *REQUESTER)
    monkeypatch.setattr(catalogs.TidalClient, "_instance", None)


# ---- Spotify: API first, embed page when the API says no


@pytest.fixture(name="fake_spotify")
async def _fake_spotify():
    """A stand-in for Spotify: the API refuses albums (like a restricted dev app), the embed page answers."""
    calls = []

    async def token(_request):
        return web.json_response({"access_token": "t", "expires_in": 3600})

    async def api_album(request):
        calls.append("api " + request.path)
        return web.json_response({"error": {"status": 403}}, status=403)

    async def api_track(request):
        calls.append("api " + request.path)
        return web.json_response(
            {"name": "Sitya Loss", "artists": [{"name": "Eddy Kenzo"}], "duration_ms": 215000, "album": {"images": []}}
        )

    async def embed(request):
        calls.append("embed " + request.path)
        return web.Response(
            text=_next_data_page(
                {
                    "type": "album",
                    "name": "Greatest Hits",
                    "trackList": [{"title": "One", "subtitle": "VJ", "duration": 1000}],
                }
            ),
            content_type="text/html",
        )

    app = web.Application()
    app.router.add_post("/token", token)
    app.router.add_get("/v1/albums/{id}", api_album)
    app.router.add_get("/v1/tracks/{id}", api_track)
    app.router.add_get("/embed/{kind}/{id}", embed)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]  # pylint: disable=protected-access
    yield f"http://127.0.0.1:{port}", calls
    await runner.cleanup()


async def test_spotify_uses_the_api_then_falls_back_to_the_embed(monkeypatch, fake_spotify):
    base, calls = fake_spotify
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "id")
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "secret")
    client = catalogs.SpotifyClient()
    client.API, client.EMBED, client.login.token_url = f"{base}/v1", f"{base}/embed", f"{base}/token"
    monkeypatch.setattr(catalogs.SpotifyClient, "_instance", client)

    tracks, title = await sources.fetch_tracks("https://open.spotify.com/track/abc", *REQUESTER)
    assert (tracks[0].search_query, title) == ("Eddy Kenzo - Sitya Loss", None)

    tracks, title = await sources.fetch_tracks("https://open.spotify.com/album/xyz", *REQUESTER)
    assert (tracks[0].search_query, title) == ("VJ - One", "Greatest Hits")

    await sources.fetch_tracks("https://open.spotify.com/playlist/p1", *REQUESTER)  # playlists: embed only
    assert calls == ["api /v1/tracks/abc", "api /v1/albums/xyz", "embed /embed/album/xyz", "embed /embed/playlist/p1"]
