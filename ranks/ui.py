"""Buttons for /ladder tidy: it shows what it would change first, and only acts once a VIP says go."""

from typing import Awaitable, Callable

import discord

# What to run when the VIP confirms. It gets the button click, so it can edit the message with the result.
OnConfirm = Callable[[discord.Interaction], Awaitable[None]]


class ConfirmTidy(discord.ui.View):
    """A "Tidy them up" / "Never mind" pair under the preview. The preview is ephemeral (only the VIP who ran
    the command can see it), so only they can press the buttons."""

    def __init__(self, on_confirm: OnConfirm):
        super().__init__(timeout=120)  # after 2 minutes the buttons stop working; run the command again
        self.on_confirm = on_confirm

    @discord.ui.button(label="Tidy them up", style=discord.ButtonStyle.danger, emoji="✂️")
    async def confirm(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.stop()  # one click only: a second press can't start a second run
        await interaction.response.edit_message(content="✂️ Snipping the old ranks off… hold the tape.", view=None)
        await self.on_confirm(interaction)

    @discord.ui.button(label="Never mind", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.stop()
        await interaction.response.edit_message(content="📼 Tape stays as it is. Nobody touched.", view=None)
