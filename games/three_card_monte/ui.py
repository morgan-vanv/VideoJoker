import logging
import random
import discord

class MonteView(discord.ui.View):
    """Class for the Three Card Monte UI"""
    CARD_LABEL = "🃏"

    def __init__(self, winning_card: str, user_id: int, invocation: discord.Interaction):
        super().__init__(timeout=30)    # times out automatically if user doesn't press a button
        self.user_id = user_id
        self.winning_card = winning_card
        self.invocation = invocation
        self.message = None

        # Randomizing button styles
        # This works because __init__() runs after the decorator function @discord.ui.button so
        # it overwrites the already existing button style when the user runs the game
        available_styles = [
            discord.ButtonStyle.primary,
            discord.ButtonStyle.success,
            discord.ButtonStyle.danger
        ]
        random.shuffle(available_styles)

        self.card_a.style = available_styles[0]
        self.card_b.style = available_styles[1]
        self.card_c.style = available_styles[2]

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

        if self.message:
            try:
                await self.message.delete()
            except Exception as e:
                logging.warning(f"Could not delete ephemeral message on timeout: {e}")

    @discord.ui.button(label=CARD_LABEL, style=discord.ButtonStyle.primary, custom_id="A")
    async def card_a(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_choice(interaction, interaction.custom_id)

    @discord.ui.button(label=CARD_LABEL, style=discord.ButtonStyle.success, custom_id="B")
    async def card_b(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_choice(interaction, interaction.custom_id)

    @discord.ui.button(label=CARD_LABEL, style=discord.ButtonStyle.danger, custom_id="C")
    async def card_c(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_choice(interaction, interaction.custom_id)
