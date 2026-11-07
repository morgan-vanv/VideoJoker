"""The buttons after /osrs register (and /osrs flexing).

It's one ephemeral (only-you-can-see-it) message that changes as you answer. The steps, in order:
  1. flexing: "Want your drops flexed?"       (only if flexing is set up and you don't have the kit yet)
  2. deaths:  "And your deaths?"              (only if you said yes to flexing and there's a deaths channel)
     → then your flexing kit, matching your answers
  3. clan:    "Is <rsn> joining the clan?"    (only while none of your accounts is in the clan)
Each step swaps the buttons, and the text keeps a running log of the answers.
"""

import logging
from typing import TYPE_CHECKING, Awaitable, Callable

import discord

from osrs import lines
from osrs.accounts import rsn_key

if TYPE_CHECKING:  # only for type hints; importing the cog for real here would be a circular import
    from cogs.osrs import Osrs

ButtonCallback = Callable[[discord.Interaction], Awaitable[None]]


class RegisterFlow(discord.ui.View):
    """flexing → deaths → (the kit) → clan → done. Steps that don't apply are skipped."""

    def __init__(self, cog: "Osrs", invocation: discord.Interaction, steps: list[str], name: str = "", intro: str = ""):
        """steps: which of "flexing", "deaths", "clan" to ask, in that order. "deaths" is asked only after a yes
        to "flexing" (or straight away when /osrs flexing starts the flow at "deaths").
        name: the account just registered (for the clan question); intro: the first line of the message."""
        super().__init__(timeout=10 * 60)
        self.cog = cog
        self.invocation = invocation  # the original command: lets us edit the message on timeout
        self.rsn = discord.utils.escape_markdown(name)  # as shown: "Iron_Morph_" shouldn't turn into italics
        self.key = rsn_key(name)  # as stored in the database
        self.log = [intro] if intro else []  # the lines shown so far; each step adds one
        self.steps = list(steps)

    def text(self) -> str:
        """The message text: every line so far."""
        return "\n".join(self.log)

    def _set_buttons(self, *buttons: tuple[str, discord.ButtonStyle, ButtonCallback]) -> None:
        """Replaces the current buttons. Each button is (label, style, what to do when pressed)."""
        self.clear_items()
        for label, style, callback in buttons:
            button = discord.ui.Button(label=label, style=style)
            button.callback = callback  # discord.py calls this with the button press's interaction
            self.add_item(button)

    def next_step(self) -> bool:
        """Puts up the next question and its buttons. Returns False when there's nothing left to ask."""
        if not self.steps:
            self.clear_items()
            self.stop()
            return False
        step = self.steps.pop(0)
        if step == "flexing":
            self.log.append(lines.FLEX_QUESTION.format(channel=self.cog.flexing_channel_mention()))
            self._set_buttons(
                ("Set me up", discord.ButtonStyle.success, self._flex_yes),
                ("Not now", discord.ButtonStyle.secondary, self._flex_no),
            )
        elif step == "deaths":
            self.log.append(lines.DEATHS_QUESTION.format(channel=self.cog.deaths_channel_mention()))
            self._set_buttons(
                ("Shame me", discord.ButtonStyle.danger, self._deaths_yes),
                ("Keep my dignity", discord.ButtonStyle.secondary, self._deaths_no),
            )
        elif step == "clan":
            self.log.append(lines.CLAN_QUESTION.format(rsn=self.rsn))
            self._set_buttons(
                ("Join the clan", discord.ButtonStyle.success, self._clan_join),
                ("Already a member", discord.ButtonStyle.primary, self._clan_member),
                ("No thanks", discord.ButtonStyle.secondary, self._clan_no),
            )
        return True

    async def _answer(self, interaction: discord.Interaction, reply: str, deferred: bool = False) -> None:
        """Swaps the question for the answer, moves on, and updates the message."""
        self.log[-1] = reply
        more = self.next_step()
        view = self if more else None
        if deferred:  # we already said "working on it" with defer(), so edit instead of responding
            await interaction.edit_original_response(content=self.text(), view=view)
        else:
            await interaction.response.edit_message(content=self.text(), view=view)

    async def _send_kit(self, interaction: discord.Interaction, reply: str, deaths: bool) -> None:
        """The last flexing answer: show the kit (matching their deaths answer), then carry on."""
        # Talking to Discord about webhooks can take a moment, and an interaction must be answered within
        # 3 seconds. defer() says "got it, working on it"; then we edit the message when we're ready.
        await interaction.response.defer()
        kit = await self.cog.flexing_kit_for(interaction.user.id, deaths)
        await self._answer(interaction, f"{reply}\n{kit}" if reply else kit, deferred=True)

    # ---- flexing

    async def _flex_yes(self, interaction: discord.Interaction) -> None:
        if self.steps and self.steps[0] == "deaths":  # ask about deaths before showing the kit
            await self._answer(interaction, lines.FLEX_YES)
        else:  # no deaths channel: straight to the kit
            await self._send_kit(interaction, lines.FLEX_YES, deaths=False)

    async def _flex_no(self, interaction: discord.Interaction) -> None:
        if self.steps and self.steps[0] == "deaths":
            self.steps.pop(0)  # no flexing means no deaths question either
        await self._answer(interaction, lines.FLEX_LATER)

    # ---- deaths

    async def _deaths_yes(self, interaction: discord.Interaction) -> None:
        await self._send_kit(interaction, lines.DEATHS_YES, deaths=True)

    async def _deaths_no(self, interaction: discord.Interaction) -> None:
        await self._send_kit(interaction, lines.DEATHS_NO, deaths=False)

    # ---- clan

    async def _answer_clan(self, interaction: discord.Interaction, answer: str, reply: str) -> None:
        await self.cog.bot.db.set_clan_answer(interaction.user.id, self.key, answer)
        await self._answer(interaction, reply)

    async def _clan_join(self, interaction: discord.Interaction) -> None:
        await self._answer_clan(interaction, "joining", lines.CLAN_JOIN.format(clan=lines.CLAN_NAME))

    async def _clan_member(self, interaction: discord.Interaction) -> None:
        await self._answer_clan(interaction, "member", lines.CLAN_ALREADY)

    async def _clan_no(self, interaction: discord.Interaction) -> None:
        await self._answer_clan(interaction, "no", lines.CLAN_NO)

    async def on_timeout(self) -> None:
        """Nobody answered for 10 minutes: remove the buttons so they can't be pressed into the void."""
        try:
            await self.invocation.edit_original_response(view=None)
        except discord.HTTPException as error:
            logging.debug("Couldn't tidy up a timed-out /osrs message: %s", error)
