"""Getting a song's audio from yt-dlp into Discord.

The chain for every song:

    yt-dlp (downloads the audio) ──pipe──▶ ffmpeg (decodes it to raw PCM) ──▶ discord.py (Opus → voice)

Why yt-dlp downloads instead of handing ffmpeg a link (the first version did that, and YouTube said 403):
YouTube signs each stream link for the client that asked for it. yt-dlp asked over IPv4 (`source_address`)
with a TV app's User-Agent; ffmpeg then fetched the link by itself, with its own User-Agent and maybe over
IPv6, so YouTube refused it. Now the same yt-dlp setup that got the link also fetches the bytes, so the request
YouTube signed is the one that downloads. It also handles SoundCloud's HLS streams (a playlist of small
chunks) with its own downloader. ffmpeg only ever sees "pipe:0", never a link.

Nothing here logs a stream link or a token: the links carry the server's IP address and YouTube's signatures.
"""

import audioop  # pylint: disable=deprecated-module  # on 3.13+ it comes from audioop-lts (with discord.py[voice])
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import threading
from urllib.parse import parse_qs, urlparse

import discord
import yt_dlp

from music import sources

# -vn: ignore any video. Audio effects (nightcore etc.) will slot in here later as an `-af` filter.
FFMPEG_OPTIONS = "-vn"
# ffmpeg reads from a pipe now, so its messages can't contain a link; keep them to real problems
FFMPEG_BEFORE = "-hide_banner -loglevel warning"

_LINK = re.compile(r"https?://\S+")
# yt-dlp's HLS downloader (SoundCloud) saves each chunk to a small file in the *current folder* before passing
# it on, even when the output is the pipe. In production the current folder (/app) is read-only, so yt-dlp
# runs in its own folder under /tmp (RAM, 256 MB; the chunks are deleted as soon as they're used).
WORK_DIR = os.path.join(tempfile.gettempdir(), "videojoker-downloads")


def describe(info: dict) -> str:
    """One log line about how yt-dlp got this stream, without the link or any token in it.

    For YouTube, the link's query string says which app ("client") yt-dlp pretended to be (c=TVHTML5 is the
    TV app) and whether a PO token (pot=) was attached. We read those two facts and throw the link away.
    """
    query = parse_qs(urlparse(info.get("url") or "").query)
    return (
        f"yt-dlp {yt_dlp.version.__version__}, {info.get('extractor_key') or '?'}, "
        f"client {query.get('c', ['-'])[0]}, format {info.get('format_id') or '?'} ({info.get('protocol') or '?'}), "
        f"PO token {'yes' if 'pot' in query else 'no'}, cookies {'yes' if sources.cookies_in_use() else 'no'}"
    )


def _log_ytdlp_errors(stream) -> None:
    """Runs in a small thread: passes yt-dlp's error messages to our log, with any link blanked out."""
    for raw in iter(stream.readline, b""):
        line = _LINK.sub("<link>", raw.decode(errors="replace").strip())
        if line:
            logging.warning("yt-dlp: %s", line)
    stream.close()


class YtdlpAudio(discord.FFmpegPCMAudio):
    """An audio source for discord.py: a yt-dlp download piped into ffmpeg.

    discord.py already knows how to feed ffmpeg from a pipe (pipe=True): a background thread copies yt-dlp's
    output into ffmpeg's input. We add starting yt-dlp before ffmpeg and stopping it after (cleanup()).
    """

    def __init__(self, info: dict):
        # yt-dlp's answer goes to the downloader as a file (--load-info-json), so it fetches exactly the
        # format we already picked, without asking YouTube again. /tmp is RAM in production; the file is
        # readable by the bot's user only (mkstemp makes it 0600) and deleted when the song ends.
        handle, self._info_path = tempfile.mkstemp(prefix="videojoker-track-", suffix=".json")
        with os.fdopen(handle, "w") as file:
            json.dump(info, file)

        command = [
            sys.executable, "-m", "yt_dlp",
            "--load-info-json", self._info_path,
            "--format", info.get("format_id") or "bestaudio/best",  # the format we picked, not yt-dlp's default
            "--output", "-",  # "-" = write the audio to stdout, i.e. into the pipe
            "--quiet", "--no-progress",
            "--source-address", "0.0.0.0",  # the same IPv4 that got the link (see sources._ytdl_options)
            "--cache-dir", str(sources.YTDLP_CACHE_DIR),
        ]  # fmt: skip
        os.makedirs(WORK_DIR, exist_ok=True)
        self._ytdlp = subprocess.Popen(  # pylint: disable=consider-using-with  # cleanup() stops it
            command, cwd=WORK_DIR, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        threading.Thread(target=_log_ytdlp_errors, args=(self._ytdlp.stderr,), daemon=True).start()
        try:
            super().__init__(self._ytdlp.stdout, pipe=True, before_options=FFMPEG_BEFORE, options=FFMPEG_OPTIONS)
        except Exception:
            self._stop_ytdlp()
            raise

    def _stop_ytdlp(self) -> None:
        if self._ytdlp.poll() is None:  # still downloading (skip, stop, or the bot shutting down)
            self._ytdlp.kill()
            try:
                self._ytdlp.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logging.warning("yt-dlp (pid %s) didn't stop within 5 s", self._ytdlp.pid)
        try:
            os.remove(self._info_path)
        except FileNotFoundError:
            pass

    def cleanup(self) -> None:
        """discord.py calls this when the song ends or is stopped: stop ffmpeg (super), then yt-dlp."""
        super().cleanup()
        self._stop_ytdlp()


class MeteredVolume(discord.PCMVolumeTransformer):
    """The volume knob from discord.py, plus a meter: it counts the 20 ms frames that go out to Discord and
    remembers the loudest one. The player logs both a few seconds into each song, so "no sound" can be told
    apart: no frames (nothing reached Discord), silent frames (the audio itself is empty), or loud frames
    (the audio is fine and gets lost between Discord and the listeners)."""

    def __init__(self, original: discord.AudioSource, volume: float = 1.0):
        super().__init__(original, volume=volume)
        self.frames = 0
        self.loudest = 0  # RMS of the loudest frame so far (0 = silence, a normal song reaches thousands)

    def read(self) -> bytes:
        frame = super().read()
        if frame:
            self.frames += 1
            self.loudest = max(self.loudest, audioop.rms(frame, 2))  # 2 = 16-bit samples
        return frame
