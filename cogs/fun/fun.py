import logging
import random
import discord
from discord.app_commands import commands
from discord.ext.commands import Cog


class Fun(Cog, name="Fun"):
    """A cog that provides fun commands"""
    def __init__(self, bot):
        logging.info("Fun cog initialized.")
        self.bot = bot

    @commands.command(name='roast', description='Roast a user')
    async def roast(self, ctx, user: discord.User):
        """Roasts a user"""
        # Update these with better roasts, maybe use an API for that?
        roasts = [
            "You're as bright as a black hole, and twice as dense.",
            "You bring everyone so much joy... when you leave the room.",
            "You're proof that even the worst people can accomplish great things.",
            "You're like a cloud. When you disappear, it's a beautiful day."
        ]
        roast = random.choice(roasts)
        logging.info("%s roasted %s: '%s'", ctx.user.name, user.name, roast)
        await ctx.response.send_message(f"{ctx.user.name} roasted {user.name}: **{roast}**")

    @commands.command(name='say', description='Repeat after me')
    async def say(self, ctx, *, message: str):
        """Repeats the given message"""
        logging.info("%s asked the bot to say: '%s'", ctx.user.name, message)
        await ctx.response.send_message(message)

async def setup(bot):
    """setup function required for loading the cog"""
    await bot.add_cog(Fun(bot))
    logging.info("Fun cog loaded.")
