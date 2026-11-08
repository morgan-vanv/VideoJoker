"""/help: the first stop for new members (the server's onboarding guide sends them here).

One card, only for the person who asked, with a short tour of what the VJ does on this server. The words live in
guide/lines.py and the "which sections to show" choice in guide/tour.py; this file only looks up what this server
has switched on and sends the card.
"""

import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from cogs.ranks import ladder_of
from guide import lines
from guide.tour import pick_sections
from ranks.ladder import tier_name

EMBED_COLOUR = discord.Colour.dark_teal()


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


class Help(commands.Cog, name="Help"):
    """**/help: a quick tour of the bot for new members**"""

    def __init__(self, bot):
        logging.info("Help cog initialized.")
        self.bot = bot

    @app_commands.command(name='help', description='New here? A quick tour of what the VJ can do. Only you see it.')
    async def tour(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild  # None in DMs
        # bot.cogs is every loaded cog by name: a feature whose cog isn't running gets no section
        sections = pick_sections(self.bot.cogs, rank_names(self.bot, guild), lobby_mention(self.bot, guild))

        description = lines.DESCRIPTION if guild else f"{lines.DESCRIPTION}\n\n{lines.IN_DMS}"
        embed = discord.Embed(title=lines.TITLE, description=description, colour=EMBED_COLOUR)
        for section in sections:
            embed.add_field(name=section.name, value=section.text, inline=False)
        embed.set_footer(text=lines.LAST_LINE)

        # ephemeral: only the person who asked sees it, so #bot-commands doesn't fill up with tours
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Help(bot))
