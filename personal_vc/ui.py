"""The control panel's buttons and the two private pickers (➕ Let in, ➖ Remove).

The panel only knows how to *ask*: each button calls back into the cog (cogs/personal_vc.py), which works out
whose channel it is and does the work. That keeps every Discord permission change in one place.
"""

from typing import Awaitable, Callable

import discord

from personal_vc import lines
from personal_vc.rules import MAX_GUESTS, Mode

# What the buttons call. They get the button click (and, for the mode buttons, which mode was pressed).
OnMode = Callable[[discord.Interaction, Mode], Awaitable[None]]
OnClick = Callable[[discord.Interaction], Awaitable[None]]
OnPick = Callable[[discord.Interaction, list[int]], Awaitable[None]]


class ControlPanel(discord.ui.View):
    """[🔓 Open] [🔒 Locked] [👻 Hidden] [➕ Let in] [➖ Remove], one row.

    The panel is posted in the chat of every new personal channel. Only that channel's owner can use it; anyone
    else who presses gets a private "not your voice channel" reply. One class serves every channel.

    This is a *persistent* view, which takes three things (a teaching moment, so here they are):
    1. timeout=None, so the buttons never stop working on their own.
    2. A fixed custom_id on every button. When someone presses a button, Discord sends the bot that id, not the
       Python object (which is gone after a restart anyway). The fixed id is how the bot recognises the button.
    3. bot.add_view(ControlPanel(...)) once at startup (the cog does it in cog_load). That tells discord.py
       "any button with these ids, on any message, goes to this view", so a panel posted last week, before a
       restart or a deploy, still works.
    Without them, the buttons on old messages would just show "This interaction failed".
    """

    def __init__(self, on_mode: OnMode, on_let_in: OnClick, on_remove: OnClick):
        super().__init__(timeout=None)
        self.on_mode = on_mode
        self.on_let_in = on_let_in
        self.on_remove = on_remove

    @discord.ui.button(label="Open", emoji="🔓", style=discord.ButtonStyle.secondary, custom_id="personalvc:open")
    async def open_up(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.on_mode(interaction, Mode.OPEN)

    @discord.ui.button(label="Locked", emoji="🔒", style=discord.ButtonStyle.secondary, custom_id="personalvc:lock")
    async def lock(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.on_mode(interaction, Mode.LOCKED)

    @discord.ui.button(label="Hidden", emoji="👻", style=discord.ButtonStyle.secondary, custom_id="personalvc:hide")
    async def hide(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.on_mode(interaction, Mode.HIDDEN)

    @discord.ui.button(label="Let in", emoji="➕", style=discord.ButtonStyle.success, custom_id="personalvc:let_in")
    async def let_in(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.on_let_in(interaction)

    @discord.ui.button(label="Remove", emoji="➖", style=discord.ButtonStyle.danger, custom_id="personalvc:remove")
    async def remove(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.on_remove(interaction)


class Picker(discord.ui.View):
    """Shared bits of the two pickers: they're private (ephemeral) and short-lived, unlike the panel."""

    def __init__(self, on_pick: OnPick):
        super().__init__(timeout=120)  # after 2 minutes the dropdown stops working; press the button again
        self.on_pick = on_pick
        # The button click that opened this picker (the cog sets it), so on_timeout can update the private message
        self.opened_by: discord.Interaction | None = None

    async def on_timeout(self) -> None:
        if self.opened_by is not None:
            try:
                await self.opened_by.edit_original_response(content=lines.PICK_EXPIRED, view=None)
            except discord.HTTPException:
                pass  # dismissed already, or Discord's 15 minutes to edit it are up: nothing to tidy

    async def picked(self, interaction: discord.Interaction, user_ids: list[int]) -> None:
        self.stop()  # one pick per dropdown: a second pick can't run twice
        await self.on_pick(interaction, user_ids)


class LetInPicker(Picker):
    """➕ Let in: Discord's own member dropdown (a UserSelect), searchable, so it works in a big server too."""

    @discord.ui.select(cls=discord.ui.UserSelect, placeholder=lines.LET_IN_PLACEHOLDER, min_values=1, max_values=10)
    async def pick(self, interaction: discord.Interaction, select: discord.ui.UserSelect) -> None:
        await self.picked(interaction, [user.id for user in select.values if not user.bot])


class RemovePicker(Picker):
    """➖ Remove: a dropdown of the current guest list. The choices depend on whose list it is, so the dropdown
    is built in __init__ instead of with a decorator."""

    def __init__(self, guests: list[tuple[int, str]], on_pick: OnPick):
        """guests: (user id, name to show) for everyone on the list."""
        super().__init__(on_pick)
        guests = guests[:MAX_GUESTS]  # a dropdown holds 25 at most (the list never gets longer, see rules.py)
        self.choice = discord.ui.Select(
            placeholder=lines.REMOVE_PLACEHOLDER,
            min_values=1,
            max_values=len(guests),
            options=[discord.SelectOption(label=name[:100], value=str(user_id)) for user_id, name in guests],
        )
        self.choice.callback = self.choose
        self.add_item(self.choice)

    async def choose(self, interaction: discord.Interaction) -> None:
        await self.picked(interaction, [int(value) for value in self.choice.values])
