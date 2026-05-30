import logging
import discord
from discord import app_commands
from discord.ext.commands import Cog

class Music(Cog, name="Music"):
    """A cog that provides music commands"""
    def __init__(self, bot):
        logging.info("Music cog initialized.")
        self.bot = bot

async def setup(bot):
    await bot.add_cog(Music(bot))
