"""Tests for core/version.py."""

from core.version import get_version


def test_local_runs_say_dev(monkeypatch):
    monkeypatch.delenv("VIDEOJOKER_VERSION", raising=False)
    assert get_version() == "dev"


def test_release_images_report_their_version(monkeypatch):
    monkeypatch.setenv("VIDEOJOKER_VERSION", "v2026.10.28")
    assert get_version() == "v2026.10.28"
