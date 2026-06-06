import logging
import random

import discord
from discord import app_commands
from discord.ext.commands import Cog

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
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This game of Three Card Monte isn't yours to play!", ephemeral=True)
            return

        if choice == self.winning_card:
            result_msg = f"{interaction.user.mention} tried to beat the odds at Three Card Monte and Won!"
        else:
            result_msg = f"{interaction.user.mention} tried to beat the odds at Three Card Monte and Lost! :("

        # Try to delete the ephemeral selection message
        try:
            await interaction.response.defer()
            await interaction.delete_original_response()
        except Exception as e:
            logging.warning(f"Could not delete ephemeral selection message: {e}. Editing instead.")
            try:
                await interaction.edit_original_response(content="Card selected! Check the main chat for results.", view=None)
            except Exception as e2:
                logging.error(f"Failed to edit ephemeral message: {e2}")

        try:
            # Update the original command invocation message with results
            await self.invocation.edit_original_response(content=result_msg)
        except discord.NotFound:
            # Fallback if the original message was somehow deleted
            await self.invocation.followup.send(result_msg)

        self.stop()

    async def on_timeout(self) -> None:
        """Handles the case where the user did not make a selection in time"""
        try:
            await self.invocation.edit_original_response(content="Three Card Monte timed out! The dealer packed up their cards.")
        except Exception:
            pass

    @discord.ui.button(label=CARD_LABEL, style=discord.ButtonStyle.primary, custom_id="A")
    async def card_a(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_choice(interaction, interaction.custom_id)

    @discord.ui.button(label=CARD_LABEL, style=discord.ButtonStyle.primary, custom_id="B")
    async def card_b(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_choice(interaction, interaction.custom_id)

    @discord.ui.button(label=CARD_LABEL, style=discord.ButtonStyle.primary, custom_id="C")
    async def card_c(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_choice(interaction, interaction.custom_id)

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

        card = random.choice(["A", "B", "C"])
        view = MonteView(winning_card=card, user_id=interaction.user.id, invocation=interaction)

        # Send the ephemeral selection message
        await interaction.followup.send(f"Pick a card, any card!", view=view, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Games(bot))
