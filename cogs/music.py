"""The VJ's music commands. Thin on purpose: commands check who's asking, then hand off to music/player.py."""
import logging

import aiohttp
import discord
from discord import app_commands
from discord.ext.commands import Cog

from music import lines
from music.player import GuildPlayer
from music.queue import LoopMode
from music.sources import SpotifyNotConfigured, TrackNotFound, fetch_tracks
from music.ui import now_playing_embed, queue_embed


class NotInVoice(app_commands.CheckFailure):
    """Raised with the VJ line to show when a voice precondition fails; the cog's error handler sends it."""


class Music(Cog, name="Music"):
    """A cog that provides music commands"""
    def __init__(self, bot):
        logging.info("Music cog initialized.")
        self.bot = bot
        self.players: dict[int, GuildPlayer] = {}  # one player per guild (server)

    # ---- helpers -------------------------------------------------------------------------------------------

    def _user_channel(self, interaction: discord.Interaction) -> discord.VoiceChannel:
        """The voice channel the user is in, or a NotInVoice error with the VJ's line."""
        voice = getattr(interaction.user, "voice", None)
        if voice is None or voice.channel is None:
            raise NotInVoice(lines.NOT_IN_VOICE)
        return voice.channel

    def _live_player(self, guild_id: int) -> GuildPlayer | None:
        """The guild's player, if it's still connected (the idle timeout disconnects quietly)."""
        player = self.players.get(guild_id)
        if player is not None and not player.voice.is_connected():
            self.players.pop(guild_id, None)
            return None
        return player

    async def _player_for(self, interaction: discord.Interaction, connect: bool) -> GuildPlayer:
        """Finds (or with connect=True, creates) the player, checking the user is in the same voice channel."""
        channel = self._user_channel(interaction)
        player = self._live_player(interaction.guild_id)
        if player is None:
            if not connect:
                raise NotInVoice(lines.NOT_CONNECTED)
            voice = await channel.connect(self_deaf=True)
            player = GuildPlayer(self.bot, voice, interaction.channel)
            self.players[interaction.guild_id] = player
            return player
        if player.voice.channel != channel:
            raise NotInVoice(lines.say(lines.WRONG_CHANNEL, channel=player.voice.channel.name))
        return player

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Shows the VJ's line for voice checks; everything else goes to the bot's global handler."""
        if isinstance(error, NotInVoice):
            if interaction.response.is_done():
                await interaction.followup.send(str(error), ephemeral=True)
            else:
                await interaction.response.send_message(str(error), ephemeral=True)
            return
        await self.bot.on_app_command_error(interaction, error)

    @Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, _before: discord.VoiceState,
                                    after: discord.VoiceState):
        """If someone kicks the VJ out of voice (or it leaves), forget the player so the next /play starts clean."""
        if member.id != self.bot.user.id or after.channel is not None:
            return
        player = self.players.pop(member.guild.id, None)
        if player is not None:
            await player.disconnect()

    # ---- commands ------------------------------------------------------------------------------------------

    @app_commands.command(name='join', description='Summons the VJ to your voice channel.')
    async def join(self, interaction: discord.Interaction) -> None:
        channel = self._user_channel(interaction)
        if self._live_player(interaction.guild_id) is not None:
            await interaction.response.send_message(lines.say(lines.ALREADY_HERE, channel=channel.name))
            return
        await self._player_for(interaction, connect=True)
        await interaction.response.send_message(lines.say(lines.JOINED, channel=channel.name))

    @app_commands.command(name='leave', description='Sends the VJ home. Clears the queue.')
    async def leave(self, interaction: discord.Interaction) -> None:
        player = self.players.pop(interaction.guild_id, None)
        if player is None:
            await interaction.response.send_message(lines.NOT_CONNECTED, ephemeral=True)
            return
        await player.disconnect()
        await interaction.response.send_message(lines.LEFT)

    @app_commands.command(name='play', description='Plays a song from a link or search query.')
    @app_commands.describe(query='A YouTube, SoundCloud or Spotify link (track, playlist, album), or words to search.',
                           play_next='Put it at the front of the queue.')
    async def play(self, interaction: discord.Interaction, query: app_commands.Range[str, 1, 500],
                   play_next: bool = False) -> None:
        # Joining voice and looking a track up can take a few seconds; deferring tells Discord "thinking..."
        # so the command doesn't time out (it has to be answered within 3 seconds otherwise).
        await interaction.response.defer()
        player = await self._player_for(interaction, connect=True)
        try:
            tracks, playlist_title = await fetch_tracks(query, interaction.user.id, interaction.user.display_name)
        except TrackNotFound:
            await interaction.followup.send(lines.say(lines.NOT_FOUND, query=query), ephemeral=True)
            return
        except SpotifyNotConfigured:
            await interaction.followup.send(lines.SPOTIFY_NOT_CONFIGURED, ephemeral=True)
            return
        except aiohttp.ClientError as error:
            logging.warning("Spotify request failed for %r: %s", query, error)
            await interaction.followup.send(lines.SPOTIFY_FAILED, ephemeral=True)
            return

        # Post the now-playing card wherever /play was last used
        player.text_channel = interaction.channel
        position = player.enqueue(tracks, play_next=play_next)

        if playlist_title:
            reply = lines.say(lines.QUEUED_MANY, count=len(tracks), title=playlist_title)
        elif play_next and player.current is not None:
            reply = lines.say(lines.QUEUED_NEXT, title=tracks[0].title)
        else:
            reply = lines.say(lines.QUEUED, title=tracks[0].title, position=position)
        await interaction.followup.send(reply)

    @app_commands.command(name='pause', description='Intermission! Pauses the current song.')
    async def pause(self, interaction: discord.Interaction) -> None:
        player = await self._player_for(interaction, connect=False)
        if player.is_paused:
            await interaction.response.send_message(lines.ALREADY_PAUSED, ephemeral=True)
            return
        player.pause()
        await interaction.response.send_message(lines.PAUSED)
        await player.refresh_now_playing()

    @app_commands.command(name='resume', description='Resumes a paused song.')
    async def resume(self, interaction: discord.Interaction) -> None:
        player = await self._player_for(interaction, connect=False)
        if not player.is_paused:
            await interaction.response.send_message(lines.NOT_PAUSED, ephemeral=True)
            return
        player.resume()
        await interaction.response.send_message(lines.RESUMED)
        await player.refresh_now_playing()

    @app_commands.command(name='skip', description='Skips the currently playing song.')
    async def skip(self, interaction: discord.Interaction) -> None:
        player = await self._player_for(interaction, connect=False)
        if not player.is_playing:
            await interaction.response.send_message(lines.NOTHING_PLAYING, ephemeral=True)
            return
        player.skip()
        await interaction.response.send_message(lines.say(lines.SKIPPED))

    @app_commands.command(name='stop', description='Stops the music and clears the queue.')
    async def stop(self, interaction: discord.Interaction) -> None:
        player = await self._player_for(interaction, connect=False)
        player.stop()
        await interaction.response.send_message(lines.STOPPED)

    @app_commands.command(name='queue', description='Shows the current music queue.')
    @app_commands.describe(page='Page number, ten songs per page.')
    async def queue(self, interaction: discord.Interaction, page: app_commands.Range[int, 1, 1000] = 1) -> None:
        player = self._live_player(interaction.guild_id)
        if player is None:
            await interaction.response.send_message(lines.NOT_CONNECTED, ephemeral=True)
            return
        await interaction.response.send_message(embed=queue_embed(player, page))

    @app_commands.command(name='nowplaying', description='Shows what the VJ is playing, with the controls.')
    async def nowplaying(self, interaction: discord.Interaction) -> None:
        player = self._live_player(interaction.guild_id)
        if player is None or player.current is None:
            await interaction.response.send_message(lines.NOTHING_PLAYING, ephemeral=True)
            return
        await interaction.response.send_message(embed=now_playing_embed(player), ephemeral=True)
        # Move the card with its buttons to this channel so people here can use them
        await player.repost_now_playing(interaction.channel)

    @app_commands.command(name='volume', description='Shows or sets the volume (0-200%).')
    @app_commands.describe(level='New volume in percent. Leave empty to see the current level.')
    async def volume(self, interaction: discord.Interaction, level: app_commands.Range[int, 0, 200] = None) -> None:
        player = await self._player_for(interaction, connect=False)
        if level is None:
            await interaction.response.send_message(lines.say(lines.VOLUME_SHOW, volume=player.volume))
            return
        player.set_volume(level)
        await interaction.response.send_message(lines.say(lines.VOLUME_SET, volume=level))
        await player.refresh_now_playing()

    @app_commands.command(name='loop', description='Loop the current song, the whole queue, or nothing.')
    @app_commands.choices(mode=[
        app_commands.Choice(name='Off', value='off'),
        app_commands.Choice(name='This song', value='track'),
        app_commands.Choice(name='Whole queue', value='queue'),
    ])
    async def loop(self, interaction: discord.Interaction, mode: app_commands.Choice[str]) -> None:
        player = await self._player_for(interaction, connect=False)
        player.queue.loop = LoopMode(mode.value)
        await interaction.response.send_message(lines.LOOP_SET[mode.value])
        await player.refresh_now_playing()

    @app_commands.command(name='shuffle', description='Shuffles the upcoming songs.')
    async def shuffle(self, interaction: discord.Interaction) -> None:
        player = await self._player_for(interaction, connect=False)
        player.queue.shuffle()
        await interaction.response.send_message(lines.SHUFFLED)
        await player.refresh_now_playing()

    @app_commands.command(name='remove', description='Removes a song from the queue by its position.')
    @app_commands.describe(position='The number shown next to the song in /queue.')
    async def remove(self, interaction: discord.Interaction, position: app_commands.Range[int, 1, 10000]) -> None:
        player = await self._player_for(interaction, connect=False)
        track = player.queue.remove(position)
        if track is None:
            await interaction.response.send_message(lines.say(lines.BAD_POSITION, position=position), ephemeral=True)
            return
        await interaction.response.send_message(lines.say(lines.REMOVED, title=track.title))
        await player.refresh_now_playing()

    @app_commands.command(name='effects', description='Applies an audio effect to the music.')
    @app_commands.choices(effect=[
        app_commands.Choice(name='Nightcore', value='nightcore'),
        app_commands.Choice(name='Bass Boosted', value='bass_boosted'),
        app_commands.Choice(name='8D Audio', value='8d_audio')
    ])
    async def effects(self, interaction: discord.Interaction, effect: app_commands.Choice[str]) -> None:

        # TODO: Implement audio effects
        await interaction.response.send_message(f"Stub: Applies effect '{effect.name}'", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Music(bot))
