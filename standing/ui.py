"""The [XP] [USh] buttons under /leaderboard."""

from typing import Optional

import discord

from standing import lines


class LeaderboardView(discord.ui.View):
    """Two buttons that swap the board between XP and USh. Both boards are worked out once, when the command runs,
    so a click just swaps one embed for the other (no database trip).

    Only the person who ran /leaderboard can switch it: the "← you" row is theirs, so someone else's click would
    show a board highlighting the wrong person. Not persistent: after a few minutes the buttons grey out."""

    def __init__(self, owner: discord.abc.User, embeds: dict[str, discord.Embed]):
        super().__init__(timeout=300)  # 5 minutes, then on_timeout greys the buttons out
        self.owner = owner
        self.embeds = embeds  # {"xp": ..., "ush": ...}
        # Set by the command right after sending, so on_timeout knows which message to edit
        self.message: Optional[discord.Message] = None
        self.highlight("xp")

    def highlight(self, board: str) -> None:
        """The button for the board on screen is blue (primary), the other one grey."""
        self.xp_button.style = discord.ButtonStyle.primary if board == "xp" else discord.ButtonStyle.secondary
        self.ush_button.style = discord.ButtonStyle.primary if board == "ush" else discord.ButtonStyle.secondary

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # discord.py runs this before any button's callback; False means the click is ignored
        if interaction.user.id == self.owner.id:
            return True
        await interaction.response.send_message(
            lines.NOT_YOUR_BOARD.format(owner=self.owner.display_name), ephemeral=True
        )
        return False

    async def show(self, interaction: discord.Interaction, board: str) -> None:
        self.highlight(board)
        await interaction.response.edit_message(embed=self.embeds[board], view=self)

    @discord.ui.button(label="XP", emoji="🎞️")
    async def xp_button(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.show(interaction, "xp")

    @discord.ui.button(label="USh", emoji="💰")
    async def ush_button(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.show(interaction, "ush")

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True
        if self.message is not None:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass  # the message was deleted, or Discord said no: nothing to grey out
