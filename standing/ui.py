"""The [XP] [USh] buttons under /leaderboard."""

from typing import Callable, Optional

import discord

# Builds one board ("xp" or "ush") as seen by one person, with their "← you" row (cogs/utility.py)
MakeEmbed = Callable[[str, discord.abc.User], discord.Embed]


class LeaderboardView(discord.ui.View):
    """Two buttons that swap the board between XP and USh. The scores are read once, when the command runs, so a
    click never needs the database.

    The board on the message belongs to whoever ran /leaderboard (the "← you" row is theirs), so only their clicks
    switch it. Anyone else who clicks gets that board privately (only they see it), with their own row: looking at
    someone's leaderboard is an invitation to check where you stand. Not persistent: after a few minutes the
    buttons grey out."""

    def __init__(self, owner: discord.abc.User, make_embed: MakeEmbed):
        super().__init__(timeout=300)  # 5 minutes, then on_timeout greys the buttons out
        self.owner = owner
        self.make_embed = make_embed
        # Set by the command right after sending, so on_timeout knows which message to edit
        self.message: Optional[discord.Message] = None
        self.highlight("xp")

    def highlight(self, board: str) -> None:
        """The button for the board on screen is blue (primary), the other one grey."""
        self.xp_button.style = discord.ButtonStyle.primary if board == "xp" else discord.ButtonStyle.secondary
        self.ush_button.style = discord.ButtonStyle.primary if board == "ush" else discord.ButtonStyle.secondary

    async def show(self, interaction: discord.Interaction, board: str) -> None:
        if interaction.user.id != self.owner.id:
            # Someone else's click: their own copy of this board, only for them. The shared message stays as it is.
            await interaction.response.send_message(
                embed=self.make_embed(board, interaction.user),
                ephemeral=True,
                allowed_mentions=discord.AllowedMentions.none(),
            )
            return
        self.highlight(board)
        await interaction.response.edit_message(embed=self.make_embed(board, self.owner), view=self)

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
