"""Guards the voice libraries against a known-silent combination.

davey 0.2 changed how Discord's voice encryption (DAVE) keys are installed, and discord.py 2.7.1 doesn't do the
new steps: the bot plays, shows the speaking ring, and nobody hears it (production, 2026-11-07). If a dependency
bump brings that pairing back, this test fails in CI instead of the music going silent in production.
"""

from importlib.metadata import version


def _major_minor(text: str) -> tuple[int, int]:
    major, minor = text.split(".")[:2]
    return int(major), int(minor)


def test_davey_works_with_this_discord_py():
    if version("discord.py") == "2.7.1":
        assert _major_minor(version("davey")) < (0, 2), (
            "davey 0.2+ makes discord.py 2.7.1 voice silent: keep davey==0.1.7 (see requirements.txt)"
        )
