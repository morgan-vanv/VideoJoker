import logging
import random
from discord.app_commands import commands
from discord.ext.commands import Cog


class Games(Cog, name="Games"):
    """A cog that provides simple game commands"""
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
        logging.info("%s flipped a coin and got: %s", ctx.user.name, result)
        await ctx.response.send_message(f"{ctx.user.name} flipped a coin and got: **{result}**")

    @commands.command(name='diceroll', description='Rolls an N sided die (defaults to 6)')
    async def diceroll(self, ctx, sides: int = 6):
        """Rolls a die, if no argument is given, defaults to 6 sides."""
        result = random.Random().randint(1, sides)
        logging.info("%s rolled a %s on a %s-sided die.", ctx.user.name, result, sides)
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
        logging.info("%s asked the 8 ball: '%s' and got: '%s'", ctx.user.name, question, answer)
        await ctx.response.send_message(f"{ctx.user.name} asked: '{question}'\n🎱 Magic 8 Ball says: **{answer}**")

    @commands.command(name='rockpaperscissors', description='Play rock-paper-scissors against the bot')
    async def rockpaperscissors(self, ctx, choice: str):
        """Play rock-paper-scissors against the bot"""
        choices = ['rock', 'paper', 'scissors']
        winning_conditions = {
            'rock': 'scissors',
            'paper': 'rock',
            'scissors': 'paper'
        }

        choice = choice.lower()
        if choice not in choices:
            await ctx.response.send_message(f"{ctx.user.name}, please choose rock, paper, or scissors.")
            return

        bot_choice = random.choice(choices)
        if choice == bot_choice:
            result = "It's a tie!"
        elif winning_conditions[choice] == bot_choice:
            result = "You win!"
        else:
            result = "I win!"

        logging.info("%s played %s against bot's %s: %s", ctx.user.name, choice, bot_choice, result)
        await ctx.response.send_message(f"{ctx.user.name} chose **{choice}**. I chose **{bot_choice}**. {result}")


async def setup(bot):
    """setup function required for loading the cog"""
    await bot.add_cog(Games(bot))
    logging.info("Games cog loaded.")
