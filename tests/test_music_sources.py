"""Tests for the parts of music/sources.py that keep yt-dlp inside the production container's rules.

In production only /app/data and /tmp are writable (CLAUDE.md, "Production hosting"). These tests don't
touch the network or Discord: they only check which options we'd hand to yt-dlp.
"""

import tempfile
from pathlib import Path

import pytest

from music import sources


@pytest.fixture(autouse=True)
def fresh_cookie_check():
    """_cookies_file() remembers its answer (functools.cache), so forget it around every test."""
    sources._cookies_file.cache_clear()  # pylint: disable=protected-access
    yield
    sources._cookies_file.cache_clear()  # pylint: disable=protected-access


def test_yt_dlp_cache_goes_in_tmp(monkeypatch):
    monkeypatch.delenv("YTDLP_COOKIES_FILE", raising=False)
    options = sources._ytdl_options()  # pylint: disable=protected-access
    assert Path(options["cachedir"]).is_relative_to(tempfile.gettempdir())


def test_deno_cache_goes_in_tmp():
    # Set when music/sources.py is imported (unless someone set DENO_DIR themselves, which CI doesn't)
    assert Path(sources.os.environ["DENO_DIR"]).is_relative_to(tempfile.gettempdir())


def test_no_cookies_configured(monkeypatch):
    monkeypatch.delenv("YTDLP_COOKIES_FILE", raising=False)
    assert "cookiefile" not in sources._ytdl_options()  # pylint: disable=protected-access


def test_writable_cookies_file_is_used(monkeypatch, tmp_path):
    cookies = tmp_path / "cookies.txt"
    cookies.write_text("# Netscape HTTP Cookie File\n")
    monkeypatch.setenv("YTDLP_COOKIES_FILE", str(cookies))
    assert sources._ytdl_options()["cookiefile"] == str(cookies)  # pylint: disable=protected-access


def test_missing_cookies_file_is_skipped(monkeypatch, tmp_path):
    monkeypatch.setenv("YTDLP_COOKIES_FILE", str(tmp_path / "nope.txt"))
    assert "cookiefile" not in sources._ytdl_options()  # pylint: disable=protected-access


def test_read_only_cookies_file_is_skipped(monkeypatch, tmp_path):
    cookies = tmp_path / "cookies.txt"
    cookies.write_text("# Netscape HTTP Cookie File\n")
    monkeypatch.setenv("YTDLP_COOKIES_FILE", str(cookies))
    # Pretend the file is read-only. (chmod wouldn't work everywhere: root can write to anything.)
    monkeypatch.setattr(sources.os, "access", lambda path, mode: False)
    assert "cookiefile" not in sources._ytdl_options()  # pylint: disable=protected-access


def test_startup_with_no_optional_settings(monkeypatch, caplog):
    for name in ("SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET", "YTDLP_COOKIES_FILE", "SOUNDCLOUD_OAUTH_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    sources.log_optional_settings()  # must not raise: the bot has to start with every extra missing
    assert "Spotify links are off" in caplog.text
