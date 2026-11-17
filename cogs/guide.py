"""/help: the first stop for new members (the server's onboarding guide sends them here), and since 2026-11-16 the
place to find every command too (it replaced /listcommands and /listadmincommands).

It opens on a short tour: the essentials (music, your own voice channel, OSRS, Minecraft) with headings, then the
rest on one line each. The dropdown under it swaps the page for one area's commands, or every command at once.
Only the person who asked sees it.

It uses Discord's newer message layout ("components v2": a LayoutView holding a Container of TextDisplays and
Separators), which can do real headings, dividers and small grey text, where an embed can't. What each page says
comes from guide/pages.py, built from guide/layout.py; this file looks up what's switched on here and puts the
pages on screen.
"""

import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from cogs.ranks import ladder_of
from guide import lines
from guide.layout import AREAS
from guide.pages import Facts, areas_on, clickable, everything, topic, tour
from ranks.ladder import tier_name

ACCENT = discord.Colour.dark_teal()


def rank_names(bot: commands.Bot, guild: Optional[discord.Guild]) -> Optional[list[str]]:
    """This server's ranks, lowest first (LOWLY SERFS, SWORN SWORDS, LORDS), or None: no ladder here, or a DM."""
    tiers = ladder_of(bot, guild)
    if not tiers:
        return None
    return [tier_name(tier) for tier in sorted(tiers, key=lambda tier: tier.number)]


def lobby_mention(bot: commands.Bot, guild: Optional[discord.Guild]) -> Optional[str]:
    """The personal-VC lobby as a channel mention, which Discord shows as a clickable link. None when there's no
    lobby to send people to: a DM, the cog isn't loaded, it was never set up here, or the channel was deleted."""
    personal_vc = bot.get_cog("PersonalVC")
    if guild is None or personal_vc is None:
        return None
    config = personal_vc.configs.get(guild.id)
    if config is None or guild.get_channel(config.hub_channel_id) is None:
        return None
    return f"<#{config.hub_channel_id}>"


def facts_for(bot: commands.Bot, guild: Optional[discord.Guild]) -> Facts:
    minecraft = bot.get_cog("Minecraft")
    return Facts(
        cogs=frozenset(bot.cogs),
        ranks=rank_names(bot, guild),
        lobby=lobby_mention(bot, guild),
        booth=getattr(minecraft, "booth", None) is not None,
    )


class HelpView(discord.ui.LayoutView):
    """One /help page on screen, with the topic dropdown under it. Picking a topic swaps the page in place."""

    def __init__(self, blocks: list[str], facts: Facts, command_ids: dict[str, int], in_dms: bool):
        super().__init__(timeout=600)  # ten minutes, then the dropdown stops answering (run /help again)
        self.facts, self.command_ids, self.in_dms = facts, command_ids, in_dms

        # The page: blocks of text with a divider between them, in one box with a coloured edge
        children = []
        for block in blocks:
            if children:
                children.append(discord.ui.Separator())
            children.append(discord.ui.TextDisplay(clickable(block, command_ids)))
        self.add_item(discord.ui.Container(*children, accent_colour=ACCENT))

        options = [discord.SelectOption(label=lines.TOUR_OPTION, value="tour")]
        options += [discord.SelectOption(label=area.name, value=area.key, emoji=area.emoji) for area in areas_on(facts)]
        options.append(discord.SelectOption(label=lines.EVERYTHING_OPTION, value="all"))
        picker = discord.ui.Select(placeholder=lines.PICK_TOPIC, options=options)

        async def picked(interaction: discord.Interaction) -> None:
            page = page_blocks(picker.values[0], self.facts, self.in_dms)
            await interaction.response.edit_message(view=HelpView(page, self.facts, self.command_ids, self.in_dms))

        picker.callback = picked
        self.add_item(discord.ui.ActionRow(picker))


def page_blocks(choice: str, facts: Facts, in_dms: bool) -> list[str]:
    """The blocks of text for what was picked in the dropdown: the tour, one area, or every command."""
    if choice == "all":
        return [everything(facts)]
    area = next((area for area in AREAS if area.key == choice), None)
    return [topic(area, facts)] if area else tour(facts, in_dms)


class Help(commands.Cog, name="Help"):
    """**/help: a quick tour of the bot, and every command**"""

    def __init__(self, bot):
        logging.info("Help cog initialized.")
        self.bot = bot

    @app_commands.command(name='help', description='New here? A tour of what the VJ can do, and every command')
    async def tour(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild  # None in DMs
        facts = facts_for(self.bot, guild)
        # command_ids: filled in when commands sync (bot.py), so the commands on the page can be tapped
        view = HelpView(tour(facts, in_dms=guild is None), facts, getattr(self.bot, "command_ids", {}), guild is None)
        # ephemeral: only the person who asked sees it, so #bot-commands doesn't fill up with tours
        await interaction.response.send_message(view=view, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Help(bot))
