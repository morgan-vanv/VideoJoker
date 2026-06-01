import logging
import discord
from discord import app_commands
from discord.ext.commands import Cog

class Music(Cog, name="Music"):
    """A cog that provides music commands"""
    def __init__(self, bot):
        logging.info("Music cog initialized.")
        self.bot = bot

    @app_commands.command(name='play', description='Plays a song from a link or search query.')
    async def play(self, interaction: discord.Interaction, query: str) -> None:

        # TODO: Implement play
        await interaction.response.send_message(f"Stub: Play song '{query}'", ephemeral=True)

    @app_commands.command(name='skip', description='Skips the currently playing song.')
    async def skip(self, interaction: discord.Interaction) -> None:

        # TODO: Implement skip
        await interaction.response.send_message("Stub: Skips the song.", ephemeral=True)

    @app_commands.command(name='queue', description='Shows the current music queue.')
    async def queue(self, interaction: discord.Interaction) -> None:

        # TODO: Implement queue
        await interaction.response.send_message("Stub: Shows the queue.", ephemeral=True)

    @app_commands.command(name='stop', description='Stops the music and clears the queue.')
    async def stop(self, interaction: discord.Interaction) -> None:

        # TODO: Implement stop
        await interaction.response.send_message("Stub: Stops music and clears queue.", ephemeral=True)

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
