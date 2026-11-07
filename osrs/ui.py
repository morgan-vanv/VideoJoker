"""The buttons after /osrs register.

It's one ephemeral (only-you-can-see-it) message that changes as you answer: maybe the clan question first,
then maybe the flexing offer. Each step swaps the buttons, and the text keeps a running log of the answers.
"""

import logging
from typing import TYPE_CHECKING, Awaitable, Callable

import discord

from osrs import lines

if TYPE_CHECKING:  # only for type hints; importing the cog for real here would be a circular import
    from cogs.osrs import Osrs

ButtonCallback = Callable[[discord.Interaction], Awaitable[None]]


class RegisterFlow(discord.ui.View):
    """Clan question (if needed) → flexing offer (if needed) → done."""

    def __init__(self, cog: "Osrs", invocation: discord.Interaction, rsn: str, key: str, intro: str):
        """rsn is the name as shown (markdown-escaped); key is its rsn_key, for the database."""
        super().__init__(timeout=10 * 60)
        self.cog = cog
        self.invocation = invocation  # the /osrs register interaction: lets us edit the message on timeout
        self.rsn, self.key = rsn, key
        self.log = [intro]  # the lines shown so far; each step adds one

    def _set_buttons(self, *buttons: tuple[str, discord.ButtonStyle, ButtonCallback]) -> None:
        """Replaces the current buttons. Each button is (label, style, what to do when pressed)."""
        self.clear_items()
        for label, style, callback in buttons:
            button = discord.ui.Button(label=label, style=style)
            button.callback = callback  # discord.py calls this with the button press's interaction
            self.add_item(button)

    def text(self) -> str:
        """The message text: every line so far."""
        return "\n".join(self.log)

    # ---- steps: each adds its question to the text and puts up its buttons

    def ask_clan(self) -> None:
        self.log.append(lines.CLAN_QUESTION.format(rsn=self.rsn))
        self._set_buttons(
            ("Join the clan", discord.ButtonStyle.success, self._clan_join),
            ("Already a member", discord.ButtonStyle.primary, self._clan_member),
            ("No thanks", discord.ButtonStyle.secondary, self._clan_no),
        )

    def offer_flexing(self, channel: discord.abc.GuildChannel) -> None:
        self.log.append(lines.FLEX_QUESTION.format(channel=channel.mention))
        self._set_buttons(
            ("Set me up", discord.ButtonStyle.success, self._flex_yes),
            ("Not now", discord.ButtonStyle.secondary, self._flex_no),
        )

    async def _next_or_finish(self, interaction: discord.Interaction) -> None:
        """After the clan answer: offer flexing if it applies, otherwise we're done."""
        channel = await self.cog.flexing_offer_channel(interaction.user.id)
        if channel:
            self.offer_flexing(channel)
            await interaction.response.edit_message(content=self.text(), view=self)
        else:
            self.stop()
            await interaction.response.edit_message(content=self.text(), view=None)

    # ---- button callbacks

    async def _answer_clan(self, interaction: discord.Interaction, answer: str, reply: str) -> None:
        await self.cog.bot.db.set_clan_answer(interaction.user.id, self.key, answer)
        self.log[-1] = reply  # replace the question with the answer
        await self._next_or_finish(interaction)

    async def _clan_join(self, interaction: discord.Interaction) -> None:
        await self._answer_clan(interaction, "joining", lines.CLAN_JOIN.format(clan=lines.CLAN_NAME))

    async def _clan_member(self, interaction: discord.Interaction) -> None:
        await self._answer_clan(interaction, "member", lines.CLAN_ALREADY)

    async def _clan_no(self, interaction: discord.Interaction) -> None:
        await self._answer_clan(interaction, "no", lines.CLAN_NO)

    async def _flex_yes(self, interaction: discord.Interaction) -> None:
        # Talking to Discord about webhooks can take a moment, and an interaction must be answered within
        # 3 seconds. defer() says "got it, working on it"; then we edit the message when we're ready.
        await interaction.response.defer()
        self.stop()
        self.log[-1] = await self.cog.flexing_kit_for(interaction.user.id)
        await interaction.edit_original_response(content=self.text(), view=None)

    async def _flex_no(self, interaction: discord.Interaction) -> None:
        self.stop()
        self.log[-1] = lines.FLEX_LATER
        await interaction.response.edit_message(content=self.text(), view=None)

    async def on_timeout(self) -> None:
        """Nobody answered for 10 minutes: remove the buttons so they can't be pressed into the void."""
        try:
            await self.invocation.edit_original_response(view=None)
        except discord.HTTPException as error:
            logging.debug("Couldn't tidy up a timed-out /osrs register message: %s", error)
