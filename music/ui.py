"""Embeds and buttons for the music player. Nothing here decides *what* plays; it only shows and forwards."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord

from music import lines
from music.queue import LoopMode, Track

if TYPE_CHECKING:  # only for type hints; avoids a circular import at runtime (player imports ui)
    from music.player import GuildPlayer

SOURCE_BADGE = {
    "youtube": ("YouTube", discord.Colour(0xFF0000)),
    "soundcloud": ("SoundCloud", discord.Colour(0xFF5500)),
    "spotify": ("Spotify", discord.Colour(0x1DB954)),
    "other": ("Link", discord.Colour.dark_grey()),
}
LOOP_ICON = {LoopMode.OFF: "➡️ off", LoopMode.TRACK: "🔂 track", LoopMode.QUEUE: "🔁 queue"}
QUEUE_PAGE_SIZE = 10


def _format_time(seconds: int) -> str:
    minutes, secs = divmod(max(0, seconds), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def progress_bar(elapsed: int, duration: int | None, width: int = 14) -> str:
    """`▬▬▬🔘▬▬▬▬▬▬▬▬▬▬ 1:03 / 3:42`, or a live marker when the length is unknown."""
    if not duration:
        return f"🔴 live · {_format_time(elapsed)}"
    filled = min(width - 1, int(width * elapsed / duration))
    bar = "▬" * filled + "🔘" + "▬" * (width - filled - 1)
    return f"{bar} `{_format_time(elapsed)} / {_format_time(duration)}`"


def _title_link(track: Track) -> str:
    return f"[{track.title}]({track.url})" if track.url else track.title


def now_playing_embed(player: GuildPlayer) -> discord.Embed:
    """The card posted when a track starts. Buttons (NowPlayingView) hang off the same message."""
    track = player.current
    badge, colour = SOURCE_BADGE.get(track.source, SOURCE_BADGE["other"])
    embed = discord.Embed(
        title=lines.INTERMISSION if player.is_paused else lines.NOW_SHOWING,
        description=f"**{_title_link(track)}**" + (f"\n{track.artist}" if track.artist else ""),
        colour=colour,
    )
    if track.thumbnail:
        embed.set_thumbnail(url=track.thumbnail)
    embed.add_field(name="\u200B", value=progress_bar(player.elapsed, track.duration), inline=False)
    embed.add_field(name="Requested by", value=track.requester_name or "someone", inline=True)
    embed.add_field(name="Source", value=badge, inline=True)
    embed.add_field(name="Loop", value=LOOP_ICON[player.queue.loop], inline=True)

    upcoming = list(player.queue.upcoming)[:3]
    if upcoming:
        preview = "\n".join(f"`{i}.` {_title_link(t)} `{t.pretty_duration}`" for i, t in enumerate(upcoming, 1))
        if len(player.queue) > 3:
            preview += f"\n…and {len(player.queue) - 3} more"
        embed.add_field(name=lines.UP_NEXT, value=preview, inline=False)

    embed.set_footer(text=f"🔊 {player.volume}%  ·  {len(player.queue)} in queue")
    return embed


def played_embed(track: Track) -> discord.Embed:
    """What a now-playing card turns into once the track is over: compact, no buttons."""
    return discord.Embed(
        description=f"📼 *Previously:* {_title_link(track)} `{track.pretty_duration}`",
        colour=discord.Colour.dark_grey(),
    )


def queue_embed(player: GuildPlayer, page: int = 1) -> discord.Embed:
    """The full programme, ten per page."""
    tracks = list(player.queue.upcoming)
    pages = max(1, (len(tracks) + QUEUE_PAGE_SIZE - 1) // QUEUE_PAGE_SIZE)
    page = max(1, min(page, pages))
    start = (page - 1) * QUEUE_PAGE_SIZE
    chunk = tracks[start:start + QUEUE_PAGE_SIZE]

    embed = discord.Embed(title="📜 Tonight's programme", colour=discord.Colour.dark_grey())
    if player.current:
        embed.add_field(name=lines.NOW_SHOWING, inline=False,
                        value=f"{_title_link(player.current)} `{player.current.pretty_duration}` "
                              f"— {player.current.requester_name}")
    if chunk:
        body = "\n".join(
            f"`{start + i}.` {_title_link(t)} `{t.pretty_duration}` — {t.requester_name}"
            for i, t in enumerate(chunk, 1)
        )
        embed.add_field(name=lines.UP_NEXT, value=body, inline=False)
    else:
        embed.add_field(name=lines.UP_NEXT, value=lines.QUEUE_EMPTY, inline=False)

    total = _format_time(player.queue.total_duration)
    embed.set_footer(text=f"Page {page}/{pages}  ·  {len(tracks)} tapes, {total} of film  ·  "
                          f"loop {LOOP_ICON[player.queue.loop]}")
    return embed


class NowPlayingView(discord.ui.View):
    """Buttons under the now-playing card. Anyone in the VJ's voice channel can press them."""

    def __init__(self, player: GuildPlayer):
        super().__init__(timeout=None)  # the message lives as long as the track; the player removes the view
        self.player = player
        self._sync_labels()

    def _sync_labels(self) -> None:
        self.pause_button.label = "Resume" if self.player.is_paused else "Pause"
        self.pause_button.emoji = "▶️" if self.player.is_paused else "⏸️"

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Runs before every button press. Keeps controls to people actually in the cinema."""
        voice_channel = self.player.voice.channel
        member_voice = getattr(interaction.user, "voice", None)
        if member_voice is None or member_voice.channel != voice_channel:
            await interaction.response.send_message(lines.say(lines.WRONG_CHANNEL, channel=voice_channel.name),
                                                    ephemeral=True)
            return False
        return True

    async def _refresh(self, interaction: discord.Interaction) -> None:
        """Edits the card in place instead of posting a new message. Less chat spam, feels like a player."""
        self._sync_labels()
        try:
            await interaction.response.edit_message(embed=now_playing_embed(self.player), view=self)
        except discord.HTTPException as error:
            logging.warning("Could not refresh now-playing card: %s", error)

    @discord.ui.button(label="Pause", emoji="⏸️", style=discord.ButtonStyle.primary, row=0)
    async def pause_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
        if self.player.is_paused:
            self.player.resume()
        else:
            self.player.pause()
        await self._refresh(interaction)

    @discord.ui.button(label="Skip", emoji="⏭️", style=discord.ButtonStyle.secondary, row=0)
    async def skip_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await interaction.response.send_message(lines.say(lines.SKIPPED))
        self.player.skip()  # the loop will retire this card and post the next one

    @discord.ui.button(label="Stop", emoji="⏹️", style=discord.ButtonStyle.danger, row=0)
    async def stop_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
        self.player.now_playing_message = None  # this card becomes the "stopped" message; don't retire it too
        self.player.stop()
        self.stop()
        await interaction.response.edit_message(content=lines.STOPPED, embed=None, view=None)

    @discord.ui.button(label="Shuffle", emoji="🔀", style=discord.ButtonStyle.secondary, row=1)
    async def shuffle_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
        self.player.queue.shuffle()
        await self._refresh(interaction)

    @discord.ui.button(label="Loop", emoji="🔁", style=discord.ButtonStyle.secondary, row=1)
    async def loop_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
        modes = list(LoopMode)
        current = modes.index(self.player.queue.loop)
        self.player.queue.loop = modes[(current + 1) % len(modes)]  # off → track → queue → off
        await self._refresh(interaction)

    @discord.ui.button(label="Queue", emoji="📜", style=discord.ButtonStyle.secondary, row=1)
    async def queue_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await interaction.response.send_message(embed=queue_embed(self.player), ephemeral=True)
