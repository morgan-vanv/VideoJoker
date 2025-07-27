import logging
import random
import discord
from discord import app_commands
from discord.ext.commands import Cog


class Fun(Cog, name="Fun"):
    """A cog that provides fun commands"""
    def __init__(self, bot):
        logging.info("Fun cog initialized.")
        self.bot = bot
    @app_commands.command(name='say', description='Repeat after me')
    async def say(self, interaction: discord.Interaction, message: str) -> None:
        """Repeats the given message"""
        logging.info("%s asked the bot to say: '%s'", interaction.user.name, message)
        await interaction.response.send_message(message)

    @app_commands.command(name='roast', description='Roast a user')
    async def roast(self, interaction: discord.Interaction, user: discord.User) -> None:
        """Roasts a user"""
        # Update these with better roasts, maybe use an API for that?
        roasts = [
            "You're as bright as a black hole, and twice as dense.",
            "You bring everyone so much joy... when you leave the room.",
            "You're proof that even the worst people can accomplish great things.",
            "You're like a cloud. When you disappear, it's a beautiful day."
        ]
        roast = random.choice(roasts)
        logging.info("%s roasted %s: '%s'", interaction.user.name, user.name, roast)
        await interaction.response.send_message(f"{interaction.user.name} roasted {user.name}: **{roast}**")

