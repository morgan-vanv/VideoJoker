"""Heartbeat: every 60 seconds while connected to Discord, write data/heartbeat.

The production host reads this file to tell "connected to Discord" apart from "the process is running".
A bot has no port to probe, so a file in the data folder (the one place the container can write) is
the simplest signal. If the file stops getting newer, the bot has lost Discord even if it hasn't crashed.

The file is one line of JSON, for example:
    {"time": "2026-11-07T18:30:00+00:00", "version": "v2026.11.07", "latency_ms": 42}
"""

import json
import logging
import math
import os
from datetime import datetime, timezone

from discord.ext import tasks
from discord.ext.commands import Cog

from core.database import DB_PATH
from core.version import get_version

# Same folder as the database (/app/data in the container)
HEARTBEAT_PATH = DB_PATH.parent / "heartbeat"


def build_heartbeat(now: datetime, version: str, latency_seconds: float) -> str:
    """Returns the heartbeat line. Kept separate from Discord so tests can check it."""
    return json.dumps(
        {
            "time": now.isoformat(timespec="seconds"),
            "version": version,
            "latency_ms": round(latency_seconds * 1000),
        }
    )


class Heartbeat(Cog, name="Heartbeat"):
    """Writes data/heartbeat every minute while the bot is connected."""

    def __init__(self, bot):
        logging.info("Heartbeat cog initialized.")
        self.bot = bot
        self.connected = False

    async def cog_load(self):
        self.beat.start()

    async def cog_unload(self):
        self.beat.cancel()

    # discord.py tells us when the connection drops and comes back; we only beat in between
    @Cog.listener()
    async def on_ready(self):
        self.connected = True

    @Cog.listener()
    async def on_resumed(self):
        self.connected = True

    @Cog.listener()
    async def on_disconnect(self):
        self.connected = False

    @tasks.loop(seconds=60)
    async def beat(self):
        latency = self.bot.latency  # seconds; NaN or infinity when there's no live connection
        if not self.connected or not math.isfinite(latency):
            return

        line = build_heartbeat(datetime.now(timezone.utc), get_version(), latency)
        temp_path = HEARTBEAT_PATH.with_suffix(".tmp")
        try:
            # Write a temp file, then swap it in: the host never reads a half-written file
            temp_path.write_text(line + "\n", encoding="utf-8")
            os.replace(temp_path, HEARTBEAT_PATH)
        except OSError as error:
            # Never let this crash: an unhandled error inside a tasks.loop stops the loop for good
            logging.warning("Could not write the heartbeat file: %s", error)

    @beat.before_loop
    async def before_beat(self):
        # The first beat waits until the bot has logged in, then the loop runs every 60 s
        await self.bot.wait_until_ready()
        self.connected = True  # logged in means connected (don't wait for on_ready above to catch up)


async def setup(bot):
    await bot.add_cog(Heartbeat(bot))
