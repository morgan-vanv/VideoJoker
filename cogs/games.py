import logging
import random

import discord
from discord import app_commands
from discord.ext.commands import Cog

from core.constants import EIGHT_BALL_RESPONSES, RPS_CHOICES, RPS_WINNING_CONDITIONS
from games import dice as dice_rules
from games.three_card_monte import MonteView, deal_winning_card


class Games(Cog, name="Games"):
    """A cog that provides simple game commands"""

    def __init__(self, bot):
        logging.info("Games cog initialized.")
        self.bot = bot

    @app_commands.command(name='coinflip', description='Flips a coin')
    async def coinflip(self, interaction: discord.Interaction) -> None:
        """Flips a coin"""
        result = random.choice(['Heads!', 'Tails!'])
        await interaction.response.send_message(f"{interaction.user.display_name} flipped a coin and got: **{result}**")

    @app_commands.command(name='roll', description='Roll dice: one six-sided die, or pick the sides and how many')
    @app_commands.describe(
        sides=f'How many sides each die has (default 6, up to {dice_rules.MAX_SIDES})',
        dice=f'How many dice to roll (default 1, up to {dice_rules.MAX_DICE})',
    )
    async def roll(self, interaction: discord.Interaction, sides: int = 6, dice: int = 1) -> None:
        """Rolls dice: /roll is one d6, /roll sides:20 dice:3 is three d20s (games/dice.py has the rules).

        A remux of Frankie's /droll and Morgan's /diceroll into one command (2026-11-16)."""
        problem = dice_rules.problem(sides, dice)
        if problem:
            await interaction.response.send_message(problem, ephemeral=True)
            return
        rolls = dice_rules.roll(sides, dice)
        await interaction.response.send_message(dice_rules.describe(interaction.user.display_name, sides, rolls))

    @app_commands.command(name='8ball', description='Ask the magic 8 ball a question')
    # Range makes Discord itself cap the question at 300 characters (the reply must fit Discord's 2000 limit)
    async def eightball(self, interaction: discord.Interaction, question: app_commands.Range[str, 1, 300]) -> None:
        """Ask the magic 8-ball a question"""
        answer = random.choice(EIGHT_BALL_RESPONSES)

        await interaction.response.send_message(
            f"{interaction.user.display_name} asked: '{question}'\n🎱 Magic 8 Ball says: **{answer}**"
        )

    @app_commands.command(name='rockpaperscissors', description='Play rock-paper-scissors against the bot')
    @app_commands.choices(
        choice=[
            app_commands.Choice(name='Rock', value='rock'),
            app_commands.Choice(name='Paper', value='paper'),
            app_commands.Choice(name='Scissors', value='scissors'),
        ]
    )
    async def rockpaperscissors(self, interaction: discord.Interaction, choice: app_commands.Choice[str]) -> None:
        """Play rock-paper-scissors against the bot"""
        user_choice = choice.value
        bot_choice = random.choice(RPS_CHOICES)
        if user_choice == bot_choice:
            result = "It's a tie!"
        elif RPS_WINNING_CONDITIONS[user_choice] == bot_choice:
            result = "You win!"
        else:
            result = "I win!"

        await interaction.response.send_message(
            f"{interaction.user.display_name} chose **{choice.name}**. I chose **{bot_choice.capitalize()}**. {result}"
        )

    @app_commands.command(name="threecardmonte", description="Play a game of Three Card Monte with the User")
    async def threecardmonte(self, interaction: discord.Interaction) -> None:
        """Runs the Three Card Monte game with the User using buttons

        1. User calls command for /threecardmonte
        2. bot sends an ephemeral message to channel with buttons selection
        3. bot deletes ephemeral message once the selection is made
        4. bot replies to the interaction with results in the message
        """

        # Respond publicly so the results can be linked to the command invocation
        await interaction.response.send_message("The dealer is shuffling the cards...", ephemeral=False)

        card = deal_winning_card()
        view = MonteView(winning_card=card, user_id=interaction.user.id, invocation=interaction)

        # Send the ephemeral selection message
        message = await interaction.followup.send("Pick a card, any card!", view=view, ephemeral=True)
        view.message = message


async def setup(bot):
    await bot.add_cog(Games(bot))
