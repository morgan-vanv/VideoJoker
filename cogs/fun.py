import logging
import random
import discord
from discord import app_commands
from discord.ext.commands import Cog

from core.constants import ROASTS


class Fun(Cog, name="Fun"):
    """A cog that provides fun commands"""
    def __init__(self, bot):
        logging.info("Fun cog initialized.")
        self.bot = bot
    @app_commands.command(name='say', description='Repeat after me')
    async def say(self, interaction: discord.Interaction, message: str) -> None:
        """Repeats the given message"""

        await interaction.response.send_message(message, allowed_mentions=discord.AllowedMentions.none())

    @app_commands.command(name='roast', description='Roast a user')
    async def roast(self, interaction: discord.Interaction, user: discord.User) -> None:
        """Roasts a user"""
        roast = random.choice(ROASTS)

        await interaction.response.send_message(f"{interaction.user.name} roasted {user.name}: **{roast}**")

    @app_commands.command(name='russianroulette', description='Play russian roulette')
    async def russianRoulette(self, interaction: discord.Interaction) -> None:
        """Game of Russian Roulette"""

        await interaction.response.send_message("Let's play Russian Roulette comrade.")

async def setup(bot):
    await bot.add_cog(Fun(bot))
