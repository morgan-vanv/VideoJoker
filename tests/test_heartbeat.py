"""Tests for the heartbeat line in cogs/heartbeat.py (the part that doesn't need Discord)."""

import json
from datetime import datetime, timezone

from cogs.heartbeat import build_heartbeat


def test_heartbeat_has_time_version_and_latency():
    now = datetime(2026, 11, 7, 18, 30, 0, tzinfo=timezone.utc)
    data = json.loads(build_heartbeat(now, "v2026.11.07", 0.0423))
    assert data == {"time": "2026-11-07T18:30:00+00:00", "version": "v2026.11.07", "latency_ms": 42}
