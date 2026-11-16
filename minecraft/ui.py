"""The buttons and the pop-up for getting someone into the game.

The path, start to finish:
  [Get me in the game]          on the welcome, the marquee and /mc status (StartView, survives restarts)
  → [Java] [Bedrock]            only you see this (EditionView)
  → a pop-up asks your name     (NameModal)
  → linked, the join card, "where to first?" [Factions] [Anarchy] [Creative]   (AfterLinkView)
/mc register jumps straight to the last step, since the command already has the name and edition.
"""

import logging
from typing import TYPE_CHECKING

import discord

from minecraft import lines
from minecraft.server import MODES

if TYPE_CHECKING:  # only for type hints; importing the cog for real here would be a circular import
    from cogs.minecraft import Minecraft

START_ID = "mc:start"  # fixed, so the button on an old message still works after a restart


class StartView(discord.ui.View):
    """The one button that starts everything. A *persistent* view: no timeout and a fixed custom_id, and the cog
    registers it at startup with bot.add_view(), so Discord's button presses find it even on week-old messages."""

    def __init__(self, cog: "Minecraft"):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label=lines.START_BUTTON, emoji="🎬", style=discord.ButtonStyle.success, custom_id=START_ID)
    async def start(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        # Anyone can press it, not just the person welcomed: each presser gets their own private flow
        await interaction.response.send_message(lines.EDITION_QUESTION, view=EditionView(self.cog), ephemeral=True)


class EditionView(discord.ui.View):
    """Java or Bedrock? Each button opens the name pop-up for that edition."""

    def __init__(self, cog: "Minecraft"):
        super().__init__(timeout=10 * 60)
        self.cog = cog

    @discord.ui.button(label=lines.JAVA_BUTTON, style=discord.ButtonStyle.primary)
    async def java(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.send_modal(NameModal(self.cog, "java"))

    @discord.ui.button(label=lines.BEDROCK_BUTTON, style=discord.ButtonStyle.primary)
    async def bedrock(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.send_modal(NameModal(self.cog, "bedrock"))


class NameModal(discord.ui.Modal):
    """A pop-up with one text box. Modals are the only way a button can ask you to type something."""

    def __init__(self, cog: "Minecraft", edition: str):
        super().__init__(title=lines.MODAL_TITLE)
        self.cog = cog
        self.edition = edition
        self.name = discord.ui.TextInput(label=lines.MODAL_LABELS[edition], min_length=1, max_length=32)
        self.add_item(self.name)

    async def on_submit(self, interaction: discord.Interaction) -> None:  # pylint: disable=arguments-differ
        await self.cog.link(interaction, self.name.value, self.edition)


class AfterLinkView(discord.ui.View):
    """ "Where to first?": one button per mode. Pressing one swaps the buttons for that mode's blurb."""

    def __init__(self, intro: str):
        super().__init__(timeout=10 * 60)
        self.intro = intro  # everything above the question: the "linked" line and the join card
        self.message_owner: discord.Interaction | None = None  # set by the cog, to tidy up on timeout
        for key, name in MODES:
            button = discord.ui.Button(label=name, style=discord.ButtonStyle.secondary)
            button.callback = self._picked(key)
            self.add_item(button)

    def text(self) -> str:
        return f"{self.intro}\n\n{lines.WHERE_FIRST}"

    def _picked(self, key: str):
        async def callback(interaction: discord.Interaction) -> None:
            self.stop()
            await interaction.response.edit_message(content=f"{self.intro}\n\n{lines.MODES[key]}", view=None)

        return callback

    async def on_timeout(self) -> None:
        """Nobody picked for 10 minutes: drop the buttons so they can't be pressed into the void."""
        if self.message_owner is None:
            return
        try:
            await self.message_owner.edit_original_response(view=None)
        except discord.HTTPException as error:
            logging.debug("Couldn't tidy up a timed-out /mc message: %s", error)
