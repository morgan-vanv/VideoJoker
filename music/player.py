"""One GuildPlayer per server. It owns the voice connection, the queue, and the loop that plays through it."""

import asyncio
import logging
import time
from importlib.metadata import PackageNotFoundError, version

import discord

from music import lines, ui
from music.queue import Queue, Track
from music.sources import TrackNotFound, resolve_stream
from music.stream import MeteredVolume, YtdlpAudio, describe

IDLE_TIMEOUT = 5 * 60  # seconds with an empty queue before the VJ packs up and leaves


class GuildPlayer:  # pylint: disable=too-many-instance-attributes
    """The play loop for one server.

    How playback works in discord.py: `voice.play(source, after=cb)` starts a background *thread* that feeds
    audio to Discord and calls `cb` when the song ends. Our loop below just waits for that callback, then
    pulls the next track. Everything else (skip, stop, pause) is a small nudge to that loop.
    """

    def __init__(self, bot, voice: discord.VoiceClient, text_channel: discord.abc.Messageable):
        self.bot = bot
        self.voice = voice
        self.text_channel = text_channel  # where now-playing cards go: the channel of the latest /play
        self.queue = Queue()
        self.volume = 100  # percent; 100 = the source's own level
        self.now_playing_message: discord.Message | None = None
        self._announced_track: Track | None = None  # the track the current card is about
        self.started_at: float | None = None  # monotonic time the current track started
        self.paused_at: float | None = None
        self.paused_total = 0.0  # seconds spent paused during the current track

        self._track_done = asyncio.Event()
        self._wake = asyncio.Event()  # set when something is added to an empty queue
        self._skip_requested = False
        self._task = bot.loop.create_task(self._play_loop())

    # ---- what the commands and buttons call --------------------------------------------------------------

    def enqueue(self, tracks: list[Track], play_next: bool = False) -> int:
        """Adds tracks and wakes the loop if it was waiting. Returns the first track's queue position."""
        if len(tracks) == 1:
            position = self.queue.add(tracks[0], play_next=play_next)
        else:
            self.queue.add_many(tracks, play_next=play_next)
            position = 1 if play_next else len(self.queue) - len(tracks) + 1
        self._wake.set()
        return position

    @property
    def current(self) -> Track | None:
        return self.queue.current

    @property
    def is_playing(self) -> bool:
        return self.voice.is_connected() and (self.voice.is_playing() or self.voice.is_paused())

    @property
    def is_paused(self) -> bool:
        return self.voice.is_paused()

    @property
    def elapsed(self) -> int:
        """Seconds into the current track, not counting time spent paused."""
        if self.started_at is None:
            return 0
        paused_now = time.monotonic() - self.paused_at if self.paused_at else 0.0
        return int(time.monotonic() - self.started_at - self.paused_total - paused_now)

    def pause(self) -> None:
        if self.voice.is_playing():
            self.voice.pause()
            self.paused_at = time.monotonic()

    def resume(self) -> None:
        if self.voice.is_paused():
            self.voice.resume()
            if self.paused_at:
                self.paused_total += time.monotonic() - self.paused_at
                self.paused_at = None

    def skip(self) -> None:
        """Stopping the current source makes discord.py fire the `after` callback, which moves the loop on."""
        self._skip_requested = True
        self.voice.stop()

    def stop(self) -> None:
        """Clears the queue and stops playback. The VJ stays in the channel until the idle timeout."""
        self.queue.clear()
        self.queue.current = None
        self.voice.stop()

    def set_volume(self, percent: int) -> None:
        self.volume = percent
        source = self.voice.source
        if isinstance(source, discord.PCMVolumeTransformer):
            source.volume = percent / 100

    async def disconnect(self, farewell: str | None = None) -> None:
        """Leaves voice and shuts the loop down, saying `farewell` first if given. The cog drops the player."""
        self._task.cancel()
        await self._retire_now_playing()
        if farewell:
            await self._announce_text(farewell)
        if self.voice.is_connected():
            await self.voice.disconnect()

    async def repost_now_playing(self, text_channel: discord.abc.Messageable) -> None:
        """Moves the now-playing card to `text_channel` (for /nowplaying, or when /play comes from elsewhere)."""
        self.text_channel = text_channel
        if self.current is not None:
            await self._announce_track(self.current)

    async def refresh_now_playing(self) -> None:
        """Re-renders the now-playing card in place (after pause, loop change, volume...)."""
        if self.now_playing_message is None or self.current is None:
            return
        try:
            await self.now_playing_message.edit(embed=ui.now_playing_embed(self))
        except discord.HTTPException as error:
            logging.warning("Could not refresh now-playing message: %s", error)

    # ---- the loop ----------------------------------------------------------------------------------------

    async def _play_loop(self) -> None:
        try:
            while True:
                track = self.queue.skip() if self._skip_requested else self.queue.advance()
                self._skip_requested = False

                if track is None:
                    await self._retire_now_playing()
                    if not await self._wait_for_tracks():
                        return
                    continue

                if not await self._start(track):
                    continue  # the track couldn't load; on to the next one
                await self._track_done.wait()
        except asyncio.CancelledError:
            pass
        except Exception:
            logging.exception("Music loop crashed in guild %s", self.voice.guild.id)

    async def _wait_for_tracks(self) -> bool:
        """Waits for something to be queued. Returns False when the VJ gave up and left."""
        self._wake.clear()
        if self.queue:  # something was queued while we were busy finishing the last track
            return True
        try:
            await asyncio.wait_for(self._wake.wait(), timeout=IDLE_TIMEOUT)
            return True
        except asyncio.TimeoutError:
            await self._announce_text(lines.IDLE_LEFT)
            if self.voice.is_connected():
                await self.voice.disconnect()
            return False

    async def _start(self, track: Track) -> bool:
        """Resolves the stream and starts ffmpeg. Returns False if the track couldn't be played."""
        try:
            await resolve_stream(track)
        except TrackNotFound:
            logging.warning("Could not resolve a stream for %r", track.title)
            await self._announce_text(lines.say(lines.LOAD_FAILED, title=track.title))
            return False

        if not self.voice.is_connected():
            return False
        await self._wait_for_voice_encryption()

        # How we got this stream (yt-dlp version, YouTube client, PO token, cookies), once per song, no links
        logging.info("Playing %r: %s", track.title, describe(track.stream_info))
        # yt-dlp downloads, ffmpeg decodes to raw PCM (see music/stream.py) so PCMVolumeTransformer can scale
        # it; discord.py then encodes to Opus. (Opus straight from ffmpeg is cheaper, but volume would be fixed.)
        try:
            audio = YtdlpAudio(track.stream_info)
        except OSError as error:  # couldn't start yt-dlp or ffmpeg at all
            logging.error("Could not start the audio pipeline for %r: %s", track.title, error)
            await self._announce_text(lines.say(lines.LOAD_FAILED, title=track.title))
            return False
        source = MeteredVolume(audio, volume=self.volume / 100)

        self._track_done.clear()
        self.started_at = time.monotonic()
        self.paused_at = None
        self.paused_total = 0.0
        try:
            self.voice.play(source, after=self._on_track_end)
        except discord.ClientException as error:
            logging.warning("voice.play failed: %s", error)
            return False

        await self._announce_track(track)
        self.bot.loop.create_task(self._voice_check(track, source))
        return True

    async def _wait_for_voice_encryption(self) -> None:
        """Discord voice calls are end-to-end encrypted (DAVE). Right after the VJ joins, it needs a moment to get
        its encryption key, and audio sent before that is dropped by everyone's Discord. So wait for the key, up to
        5 s, before starting the song. Only reads discord.py internals defensively: no key info, no harm done."""
        connection = getattr(self.voice, "_connection", None)
        if not getattr(connection, "dave_protocol_version", 0):
            return  # not an encrypted call (or an older discord.py): nothing to wait for
        for _ in range(50):
            if getattr(connection, "can_encrypt", False):
                return
            await asyncio.sleep(0.1)
        logging.warning(
            "Voice encryption key still missing after 5 s (davey %s): listeners may hear nothing. "
            "See tests/test_voice_deps.py.",
            _davey_version(),
        )

    async def _voice_check(self, track: Track, source: MeteredVolume) -> None:
        """Five seconds into a song, logs whether audio is really going out, and how it's encrypted.

        DAVE is Discord's end-to-end encryption for voice. If the bot's DAVE session isn't ready ("encrypting:
        no") while the call expects it, listeners get audio they can't decode: silence, with a speaking ring.
        The voice details come from discord.py internals, so every read is guarded: this must never break playback.
        """
        await asyncio.sleep(5)
        if self.current is not track or not self.voice.is_connected():
            return
        connection = getattr(self.voice, "_connection", None)
        dave_version = getattr(connection, "dave_protocol_version", "?")
        encrypting = getattr(connection, "can_encrypt", "?")
        original = source.original  # the YtdlpAudio inside the volume knob
        download = original.status() if isinstance(original, YtdlpAudio) else "?"
        logging.info(
            "Voice check for %r after 5 s: %s, %s frames sent, loudest rms %s, DAVE protocol %s, encrypting %s, "
            "privacy code %s, transport %s, channel members %s, davey %s",
            track.title,
            download,
            source.frames,
            source.loudest,
            dave_version,
            encrypting,
            "yes" if getattr(self.voice, "voice_privacy_code", None) else "no",
            getattr(self.voice, "mode", "?"),
            len(getattr(self.voice.channel, "members", [])),
            _davey_version(),
        )

    def _on_track_end(self, error: Exception | None) -> None:
        """Runs on discord.py's audio thread, not the event loop. That's why we go through call_soon_threadsafe:
        touching asyncio objects from another thread is a classic source of 'why does it hang sometimes' bugs."""
        if error:
            logging.error("Audio player error: %s", error)
        self.bot.loop.call_soon_threadsafe(self._track_done.set)

    # ---- messages ----------------------------------------------------------------------------------------

    async def _announce_track(self, track: Track) -> None:
        """Retires the previous now-playing card and posts a fresh one with buttons."""
        await self._retire_now_playing()
        self._announced_track = track
        try:
            self.now_playing_message = await self.text_channel.send(
                embed=ui.now_playing_embed(self), view=ui.NowPlayingView(self)
            )
        except discord.HTTPException as error:
            logging.warning("Could not post now-playing message for %r: %s", track.title, error)

    async def _retire_now_playing(self) -> None:
        """Turns the old card into a compact 'played' card with no buttons, so stale buttons never linger."""
        message, self.now_playing_message = self.now_playing_message, None
        if message is None or self._announced_track is None:
            return
        try:
            await message.edit(embed=ui.played_embed(self._announced_track), view=None)
        except discord.HTTPException:
            pass

    async def _announce_text(self, text: str) -> None:
        try:
            await self.text_channel.send(text)
        except discord.HTTPException as error:
            logging.warning("Could not send to music channel: %s", error)


def _davey_version() -> str:
    """The installed davey (the voice encryption library), for the log. "missing" if it isn't installed."""
    try:
        return version("davey")
    except PackageNotFoundError:
        return "missing"
