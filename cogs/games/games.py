import logging
import random
import asyncio
import discord
from discord.app_commands import commands
from discord.ext.commands import Cog


# This cog provides simple games.
class Games(Cog, name="Games"):
    def __init__(self, bot):
        logging.info("Games cog initialized.")
        self.bot = bot

    @commands.command()
    async def coinflip(self, ctx):
        """Flips a coin"""
        if random.Random().randint(0, 1) == 0:
            await ctx.response.send_message('Heads!')
        else:
            await ctx.response.send_message('Tails!')

async def setup(bot):
    await bot.add_cog(Games(bot))
    logging.info("Games cog loaded.")
