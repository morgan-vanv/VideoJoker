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
            result = 'Heads!'
        else:
            result = 'Tails!'
        logging.info(f"{ctx.user.name} flipped a coin and got: {result}")
        await ctx.response.send_message(f"{ctx.user.name} flipped a coin and got: **{result}**")

    @commands.command(name='diceroll', description='Rolls an N sided die (defaults to 6)')
    async def diceroll(self, ctx, sides: int = 6):
        """Rolls a die, if no argument is given, defaults to 6 sides."""
        result = random.Random().randint(1, sides)
        logging.info(f"{ctx.user.name} rolled a {result} on a {sides}-sided die.")
        await ctx.response.send_message(f"{ctx.user.name} rolled a **{result}** on a {sides}-sided die.")

    @commands.command(name='8ball', description='Ask the magic 8 ball a question')
    async def eightball(self, ctx, *, question: str):
        """Ask the magic 8-ball a question"""
        responses = [
            "It is certain.", "It is decidedly so.", "Without a doubt.", "Yes - definitely.",
            "You may rely on it.", "As I see it, yes.", "Most likely.", "Outlook good.",
            "Yes.", "Signs point to yes.", "Reply hazy, try again.", "Ask again later.",
            "Better not tell you now.", "Cannot predict now.", "Concentrate and ask again.",
            "Don't count on it.", "My reply is no.", "My sources say no.", "Outlook not so good.",
            "Very doubtful."
        ]
        answer = random.choice(responses)
        logging.info(f"{ctx.user.name} asked the 8 ball: '{question}' and got: '{answer}'")
        await ctx.response.send_message(f"{ctx.user.name} asked: '{question}'\n🎱 Magic 8 Ball says: **{answer}**")


async def setup(bot):
    await bot.add_cog(Games(bot))
    logging.info("Games cog loaded.")
