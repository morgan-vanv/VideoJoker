import logging
import random

import discord
from discord import app_commands
from discord.ext.commands import Cog

from core.constants import EIGHT_BALL_RESPONSES, RPS_CHOICES, RPS_WINNING_CONDITIONS
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
        await interaction.response.send_message(f"{interaction.user.name} flipped a coin and got: **{result}**")

    @app_commands.command(name='diceroll', description='Rolls an N-sided die (defaults to 6)')
    async def diceroll(self, interaction: discord.Interaction, sides: int = 6) -> None:
        """Rolls a die, if no argument is given, defaults to 6 sides."""
        if sides < 1:
            await interaction.response.send_message("A die must have at least 1 side!", ephemeral=True)
            return

        result = random.randint(1, sides)
        await interaction.response.send_message(f"{interaction.user.name} rolled a **{result}** on a {sides}-sided die.")

    @app_commands.command(name='8ball', description='Ask the magic 8 ball a question')
    async def eightball(self, interaction: discord.Interaction, question: str) -> None:
        """Ask the magic 8-ball a question"""
        answer = random.choice(EIGHT_BALL_RESPONSES)

        await interaction.response.send_message(f"{interaction.user.name} asked: '{question}'\n🎱 Magic 8 Ball says: **{answer}**")

    @app_commands.command(name='rockpaperscissors', description='Play rock-paper-scissors against the bot')
    @app_commands.choices(choice=[
        app_commands.Choice(name='Rock', value='rock'),
        app_commands.Choice(name='Paper', value='paper'),
        app_commands.Choice(name='Scissors', value='scissors')
    ])
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

        await interaction.response.send_message(f"{interaction.user.name} chose **{choice.name}**. I chose **{bot_choice.capitalize()}**. {result}")

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
        message = await interaction.followup.send(f"Pick a card, any card!", view=view, ephemeral=True)
        view.message = message

async def setup(bot):
    await bot.add_cog(Games(bot))
