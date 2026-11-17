"""The two dropdowns under /osrs accounts and /mc accounts: "make one your main" and "unlink one". They replaced
/osrs default, /osrs remove, /mc default and /mc remove on 2026-11-16 (fewer commands in the / menu).

Shared by both games, so it only knows about choices, not accounts: each cog gives it (value, label, is main?)
for every account and two functions to call when someone picks one. The message is only theirs (ephemeral), so
nobody else can click these.
"""

from typing import Awaitable, Callable, NamedTuple

import discord

# What a cog does when an account is picked: (the click, the picked account's value) → edits the message itself
OnPick = Callable[[discord.Interaction, str], Awaitable[None]]


class AccountChoice(NamedTuple):
    value: str  # what the cog uses to find the account again (an OSRS name key, a Minecraft UUID)
    label: str  # what the person sees
    is_main: bool


class AccountsView(discord.ui.View):
    def __init__(self, choices: list[AccountChoice], on_main: OnPick, on_unlink: OnPick):
        super().__init__(timeout=600)  # ten minutes, then the dropdowns stop answering (run the command again)
        others = [choice for choice in choices if not choice.is_main]
        if others:  # only worth offering with two accounts or more
            main = discord.ui.Select(
                placeholder="⭐ Make one your main…",
                options=[discord.SelectOption(label=c.label[:100], value=c.value) for c in others[:25]],
            )

            async def picked_main(interaction: discord.Interaction) -> None:
                await on_main(interaction, main.values[0])

            main.callback = picked_main
            self.add_item(main)

        unlink = discord.ui.Select(
            placeholder="Unlink one…",
            options=[discord.SelectOption(label=c.label[:100], value=c.value) for c in choices[:25]],
        )

        async def picked_unlink(interaction: discord.Interaction) -> None:
            await on_unlink(interaction, unlink.values[0])

        unlink.callback = picked_unlink
        self.add_item(unlink)
