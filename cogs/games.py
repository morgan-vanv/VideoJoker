import logging
import random
from email import message
from unittest import result

import discord
from dill.pointers import parent
from discord import app_commands, Interaction
from discord._types import ClientT
from discord.ext.commands import Cog, context

from core.constants import EIGHT_BALL_RESPONSES, RPS_CHOICES, RPS_WINNING_CONDITIONS

class MonteView(discord.ui.View):
    """Class for the Three Card Monte UI"""
    CARD_LABEL = "🃏"

    def __init__(self, winning_card: str, user_id: int, invocation: discord.Interaction):
        super().__init__(timeout=30)    # times out automatically if user doesn't press a button
        self.user_id = user_id
        self.winning_card = winning_card
        self.invocation = invocation

    async def handle_choice(self, interaction: discord.Interaction, choice: str) -> None:
        """Handles the user's choice and clears the response"""
        if choice == self.winning_card:
            result_msg = f"{interaction.user.mention} tried to beat the odds at Three Card Monte and Won!"
        else:
            result_msg = f"{interaction.user.mention} tried to beat the odds at Three Card Monte and Lost! :("

        await interaction.response.defer()
        await self.invocation.delete_original_response()
        # await interaction.delete_original_response()
        # logging.warning(self.invocation)
        await self.invocation.followup.send(result_msg, ephemeral=False)

        self.stop()

    # Functions that create the buttons - I would like to customize the look of the buttons a bit more
    @discord.ui.button(label=CARD_LABEL, style=discord.ButtonStyle.primary, custom_id="A")
    async def card_a(self, interaction: discord.Interaction, temp):
        # Logging interaction when card_a button is clicked
        # logging.warning(interaction)
        # logging.warning(interaction.custom_id)

        await self.handle_choice(interaction, interaction.custom_id)

    @discord.ui.button(label=CARD_LABEL, style=discord.ButtonStyle.primary, custom_id="B")
    async def card_b(self, interaction: discord.Interaction, temp):
        await self.handle_choice(interaction, interaction.custom_id)

    @discord.ui.button(label=CARD_LABEL, style=discord.ButtonStyle.primary, custom_id="C")
    async def card_c(self, interaction: discord.Interaction, temp):
        await self.handle_choice(interaction, interaction.custom_id)

class Games(Cog, name="Games"):
    """A cog that provides simple game commands"""
    def __init__(self, bot):
        logging.info("Games cog initialized.")
        self.bot = bot

    @app_commands.command()
    async def coinflip(self, interaction: discord.Interaction) -> None:
        """Flips a coin"""
        if random.Random().randint(0, 1) == 0:
            result = 'Heads!'
        else:
            result = 'Tails!'

        await interaction.response.send_message(f"{interaction.user.name} flipped a coin and got: **{result}**")

    @app_commands.command(name='diceroll', description='Rolls an N sided die (defaults to 6)')
    async def diceroll(self, interaction: discord.Interaction, sides: int = 6) -> None:
        """Rolls a die, if no argument is given, defaults to 6 sides."""
        result = random.Random().randint(1, sides)

        await interaction.response.send_message(f"{interaction.user.name} rolled a **{result}** on a {sides}-sided die.")

    @app_commands.command(name='8ball', description='Ask the magic 8 ball a question')
    async def eightball(self, interaction: discord.Interaction, question: str) -> None:
        """Ask the magic 8-ball a question"""
        answer = random.choice(EIGHT_BALL_RESPONSES)

        await interaction.response.send_message(f"{interaction.user.name} asked: '{question}'\n🎱 Magic 8 Ball says: **{answer}**")

    @app_commands.command(name='rockpaperscissors', description='Play rock-paper-scissors against the bot')
    async def rockpaperscissors(self, interaction: discord.Interaction, choice: str) -> None:
        """Play rock-paper-scissors against the bot"""
        choice = choice.lower()
        if choice not in RPS_CHOICES:
            await interaction.response.send_message(f"{interaction.user.name}, please choose rock, paper, or scissors.")
            return

        bot_choice = random.choice(RPS_CHOICES)
        if choice == bot_choice:
            result = "It's a tie!"
        elif RPS_WINNING_CONDITIONS[choice] == bot_choice:
            result = "You win!"
        else:
            result = "I win!"


        await interaction.response.send_message(f"{interaction.user.name} chose **{choice}**. I chose **{bot_choice}**. {result}")

    @app_commands.command(name="threecardmonte", description="Play a game of Three Card Monte with the User")
    async def threecardmonte(self, interaction: discord.Interaction) -> None:
        """Runs the Three Card Monte game with the User using buttons

            1. User calls command for /threecardmonte
            2. bot sends an ephemeral message to channel with buttons selection
            3. bot deletes ephemeral message once the selection is made
            4. bot replies to the interaction with results in the message
        """

        card = random.choice(["A", "B", "C"])
        view = MonteView(winning_card=card, user_id=interaction.user.id, invocation=interaction)

        await interaction.response.send_message(f"Pick a card, any card!", view=view, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Games(bot))
