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
import collections
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from urllib.parse import parse_qs, urlparse

import discord
import yt_dlp

from music import sources

# Every song is evened out to the same loudness with ffmpeg's loudnorm filter (the EBU R128 broadcast standard),
# so YouTube and SoundCloud sound alike. -26 LUFS is well below streaming apps (about -14), so nobody joining the
# call gets blasted; /volume 200 doubles the signal (+6), which brings it back up to about -20.
# I = target loudness in LUFS (lower = quieter), TP = loudest peak allowed, LRA = how much the loudness may vary.
LOUDNESS = "loudnorm=I=-26:TP=-2:LRA=11"
# -vn: ignore any video. Audio effects (nightcore etc.) will slot in later, chained onto the same -af filter.
FFMPEG_OPTIONS = f"-vn -af {LOUDNESS}"
PREBUFFER_BYTES = 64 * 1024  # wait for ~3 s of YouTube audio (or the whole song, if shorter) before playing
PREBUFFER_TIMEOUT = 5  # seconds; after that, start anyway
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


class _ReadAhead:
    """Downloads ahead of playback, so a slow moment on the network isn't a stutter.

    Without it, yt-dlp writes into a small pipe (about 64 KB, ~3 s of YouTube audio) that only empties as fast
    as Discord plays. yt-dlp is held back to playback speed, its connection to YouTube sits mostly idle, and
    YouTube drops idle connections: every reconnect is a gap, and a gap longer than the few seconds in the pipe
    is a stutter (discord.py then rushes the late frames out, which sounds like a tempo jump).

    So a small thread reads yt-dlp's output as fast as it comes into memory, up to LIMIT bytes ahead (32 MB is
    ~25 min of YouTube audio), and ffmpeg is fed from that buffer. The chunks sit in a deque (a list that's
    cheap to take from the front), and a Condition lets the two threads wait for each other without busy-looping.
    """

    CHUNK = 64 * 1024
    LIMIT = 32 * 1024 * 1024

    def __init__(self, pipe):
        self._pipe = pipe
        self._chunks: collections.deque[bytes] = collections.deque()
        self._buffered = 0  # bytes waiting in _chunks
        self._finished = False  # yt-dlp's output has ended (or we're closing)
        self._changed = threading.Condition()
        self.received = 0  # total bytes yt-dlp has delivered (for the voice check)
        self.started_at = time.monotonic()
        threading.Thread(target=self._fill, name="yt-dlp read-ahead", daemon=True).start()

    def _fill(self) -> None:
        try:
            while True:
                with self._changed:
                    while self._buffered >= self.LIMIT and not self._finished:
                        self._changed.wait()  # far enough ahead: wait for playback to catch up a bit
                    if self._finished:
                        return
                chunk = self._pipe.read1(self.CHUNK)  # whatever has arrived, up to CHUNK bytes
                if not chunk:
                    return  # yt-dlp finished (or was stopped)
                with self._changed:
                    if self._finished:  # close() ran while we were reading: drop it
                        return
                    self._chunks.append(chunk)
                    self._buffered += len(chunk)
                    self.received += len(chunk)
                    self._changed.notify_all()
        except OSError, ValueError:  # the pipe was closed under us while stopping
            pass
        finally:
            with self._changed:
                self._finished = True
                self._changed.notify_all()

    def wait_for(self, size: int, timeout: float) -> None:
        """Waits until `size` bytes are buffered, the download has ended, or `timeout` seconds have passed."""
        with self._changed:
            self._changed.wait_for(lambda: self._buffered >= size or self._finished, timeout=timeout)

    def read(self, size: int = -1) -> bytes:
        """What discord.py's feeder thread calls: up to `size` bytes, waiting if none are there yet; b"" = the end."""
        with self._changed:
            self._changed.wait_for(lambda: self._chunks or self._finished)
            if not self._chunks:
                return b""
            chunk = self._chunks.popleft()
            if 0 <= size < len(chunk):  # give part of it, keep the rest at the front
                chunk, rest = chunk[:size], chunk[size:]
                self._chunks.appendleft(rest)
            self._buffered -= len(chunk)
            self._changed.notify_all()
            return chunk

    def close(self) -> None:
        with self._changed:
            self._finished = True
            self._chunks.clear()
            self._buffered = 0
            self._changed.notify_all()

    def status(self) -> str:
        seconds = max(time.monotonic() - self.started_at, 0.001)
        return (
            f"{self.received} bytes from yt-dlp ({self.received / seconds / 1024:.0f} KB/s), {self._buffered} buffered"
        )


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
        self.downloaded = _ReadAhead(self._ytdlp.stdout)
        try:
            super().__init__(self.downloaded, pipe=True, before_options=FFMPEG_BEFORE, options=FFMPEG_OPTIONS)
        except Exception:
            self._stop_ytdlp()
            raise

    def _pipe_writer(self, source) -> None:
        """discord.py's background thread that copies our download into ffmpeg's input, with one change: flush().

        Python 3.14 gives every pipe a 128 KB buffer (it was 8 KB), and discord.py's own copy of this loop never
        flushes it. So ffmpeg only got audio once 128 KB had piled up: ~6 s of YouTube audio at a time, and any
        slow moment on the network became a stutter. Flushing after every piece hands it to ffmpeg straight away.
        """
        while self._process:
            data = source.read(self.BLOCKSIZE)
            stdin = self._stdin
            if not stdin:  # cleanup() already ran
                return
            try:
                if not data:  # the download has ended: closing ffmpeg's input tells it to finish
                    stdin.close()
                    return
                stdin.write(data)
                stdin.flush()
            except OSError, ValueError:  # ffmpeg has stopped (skip, or the song is over)
                return

    def prebuffer(self) -> None:
        """Waits (up to PREBUFFER_TIMEOUT s) until a few seconds of audio are downloaded, so playback starts with a
        cushion. It blocks, so the player runs it in a worker thread (asyncio.to_thread), never on the event loop."""
        self.downloaded.wait_for(PREBUFFER_BYTES, timeout=PREBUFFER_TIMEOUT)

    def _stop_ytdlp(self) -> None:
        if self._ytdlp.poll() is None:  # still downloading (skip, stop, or the bot shutting down)
            self._ytdlp.kill()
            try:
                self._ytdlp.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logging.warning("yt-dlp (pid %s) didn't stop within 5 s", self._ytdlp.pid)
        self.downloaded.close()
        try:
            os.remove(self._info_path)
        except FileNotFoundError:
            pass

    def status(self) -> str:
        """For the voice check: bytes yt-dlp has delivered so far, and whether yt-dlp and ffmpeg are still running
        (an exit code means it has stopped)."""
        ffmpeg = getattr(self, "_process", None)  # discord.py's ffmpeg process (a placeholder once cleaned up)
        ffmpeg_state = ffmpeg.poll() if isinstance(ffmpeg, subprocess.Popen) else "?"
        return (
            f"{self.downloaded.status()}, "
            f"yt-dlp {'running' if self._ytdlp.poll() is None else f'exited {self._ytdlp.returncode}'}, "
            f"ffmpeg {'running' if ffmpeg_state is None else f'exited {ffmpeg_state}'}"
        )

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
