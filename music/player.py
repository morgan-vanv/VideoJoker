"""One GuildPlayer per server. It owns the voice connection, the queue, and the loop that plays through it."""
import asyncio
import logging
import time

import discord

from music import lines, ui
from music.queue import Queue, Track
from music.sources import TrackNotFound, resolve_stream

# Tell ffmpeg to reconnect if the audio host drops the connection mid-song (common with YouTube) and to
# ignore any video stream. Audio effects (nightcore etc.) will slot in here later as an `-af` filter.
FFMPEG_BEFORE = "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
FFMPEG_OPTIONS = "-vn"

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
        self.text_channel = text_channel      # where now-playing cards go: the channel of the latest /play
        self.queue = Queue()
        self.volume = 100                     # percent; 100 = the source's own level
        self.now_playing_message: discord.Message | None = None
        self._announced_track: Track | None = None  # the track the current card is about
        self.started_at: float | None = None  # monotonic time the current track started
        self.paused_at: float | None = None
        self.paused_total = 0.0               # seconds spent paused during the current track

        self._track_done = asyncio.Event()
        self._wake = asyncio.Event()          # set when something is added to an empty queue
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

    async def disconnect(self) -> None:
        """Leaves voice and shuts the loop down. The cog drops the player afterwards."""
        self._task.cancel()
        await self._retire_now_playing()
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

        # FFmpegPCMAudio decodes to raw PCM so PCMVolumeTransformer can scale it; discord.py then encodes
        # to Opus. (FFmpegOpusAudio is cheaper on CPU but then volume can't be changed mid-song.)
        audio = discord.FFmpegPCMAudio(track.stream_url, before_options=FFMPEG_BEFORE, options=FFMPEG_OPTIONS)
        source = discord.PCMVolumeTransformer(audio, volume=self.volume / 100)

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
        return True

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
