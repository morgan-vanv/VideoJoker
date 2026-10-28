"""Which version of VideoJoker is running.

Release images get their version baked in at build time (see .github/workflows/release.yml and the
Dockerfile), e.g. "v2026.10.28". Anything built or run on your own machine says "dev".
"""
import os


def get_version() -> str:
    """Returns the running version, or "dev" for local builds."""
    return os.getenv("VIDEOJOKER_VERSION") or "dev"
