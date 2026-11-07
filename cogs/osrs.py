"""The /osrs commands: link your Old School RuneScape accounts, see who plays what, and set up drop flexing.

Design and the why behind it: docs/osrs-design.md. The pieces live in osrs/ (name rules, Wise Old Man,
webhooks, buttons, the VJ's lines); this file is the thin layer that turns slash commands into calls to them.
"""

import logging
from typing import Optional

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from cogs.permissions import is_vip
from core.database import OsrsAccount
from osrs import flexing, lines, wom
from osrs.accounts import clean_rsn, rsn_key
from osrs.ui import RegisterFlow

EMBED_COLOUR = discord.Colour.from_str("#B0B57B")  # the same olive as the Dink embeds (swannobi's embedColor)
MENTIONS_PER_MESSAGE = 50  # a ping message must stay under Discord's 2,000 characters; a mention is ~22


# GroupCog turns every command in this class into a subcommand: register becomes "/osrs register".
# guild_only: these commands only make sense in a server (DMs have no flexing channel or members to look up).
@app_commands.guild_only()
class Osrs(commands.GroupCog, group_name="osrs", group_description="Link your OSRS accounts and flex your drops."):
    """Old School RuneScape: account linking and drop flexing"""

    def __init__(self, bot):
        logging.info("OSRS cog initialized.")
        self.bot = bot
        self.session: Optional[aiohttp.ClientSession] = None

    async def cog_load(self):
        # One web session for the cog's whole life (for Wise Old Man), closed again on shutdown
        self.session = aiohttp.ClientSession()

    async def cog_unload(self):
        if self.session:
            await self.session.close()

    # ---- helpers (also used by the buttons in osrs/ui.py)

    async def clan_keys(self) -> Optional[frozenset[str]]:
        """Who's in the clan, per Wise Old Man; None if WOM can't be reached."""
        return await wom.clan_member_keys(self.session)

    @staticmethod
    def in_clan(account: OsrsAccount, clan: Optional[frozenset[str]]) -> bool:
        """An account counts as in the clan if they told us so, or Wise Old Man says so."""
        return account.clan_answer == "member" or (clan is not None and account.rsn_key in clan)

    async def flexing_offer_channel(self, user_id: int) -> Optional[discord.TextChannel]:
        """The flexing channel, if flexing is set up and this person hasn't got the webhook yet."""
        try:
            channel, _ = flexing.flexing_channels(self.bot)
        except flexing.FlexingNotSetUp:
            return None
        return None if await self.bot.db.is_flexer(user_id) else channel

    async def flexing_kit_for(self, user_id: int) -> str:
        """The flexing kit text (and remember them as a flexer), or a message saying what's missing."""
        try:
            kit = await flexing.make_kit(self.bot)
        except flexing.FlexingNotSetUp:
            return lines.FLEX_NOT_SET_UP
        except discord.Forbidden:
            channel, _ = flexing.flexing_channels(self.bot)
            return lines.FLEX_NO_PERMISSION.format(channel=channel.mention)
        await self.bot.db.add_flexer(user_id)
        return kit

    async def accounts_embed(self, member: discord.abc.User, accounts: list[OsrsAccount]) -> discord.Embed:
        clan = await self.clan_keys()
        rows = []
        for account in accounts:
            marks = (" ⭐" if account.is_default else "") + (" 🏰" if self.in_clan(account, clan) else "")
            rows.append(f"**{discord.utils.escape_markdown(account.rsn)}**{marks}")
        embed = discord.Embed(
            title=f"📼 {member.display_name}'s tapes", description="\n".join(rows), colour=EMBED_COLOUR
        )
        embed.set_footer(text=lines.ACCOUNTS_LEGEND)
        return embed

    # ---- commands

    @app_commands.command(name="register", description="Link an OSRS account to your Discord (alts welcome)")
    @app_commands.describe(rsn="The account's in-game name")
    async def register(self, interaction: discord.Interaction, rsn: str) -> None:
        name = clean_rsn(rsn)
        if name is None:
            await interaction.response.send_message(
                lines.INVALID_RSN.format(rsn=discord.utils.escape_markdown(rsn)), ephemeral=True
            )
            return

        key = rsn_key(name)
        shown = discord.utils.escape_markdown(name)  # so "Iron_Morph_" doesn't turn into italics
        owner = await self.bot.db.add_osrs_account(interaction.user.id, name, key)
        if owner == interaction.user.id:
            await interaction.response.send_message(lines.ALREADY_YOURS.format(rsn=shown), ephemeral=True)
            return
        if owner is not None:
            # <@id> shows as their name; it doesn't ping anyone because the message is ephemeral
            await interaction.response.send_message(lines.TAKEN.format(rsn=shown, owner=f"<@{owner}>"), ephemeral=True)
            return

        # Asking Wise Old Man can take a second, and Discord wants an answer within 3: defer first
        await interaction.response.defer(ephemeral=True)
        accounts = await self.bot.db.get_osrs_accounts(interaction.user.id)
        this_one = next(account for account in accounts if account.rsn_key == key)
        intro = lines.REGISTERED.format(rsn=shown) + (lines.REGISTERED_DEFAULT if this_one.is_default else "")

        flow = RegisterFlow(self, interaction, shown, key, intro)
        clan = await self.clan_keys()
        flex_channel = await self.flexing_offer_channel(interaction.user.id)
        if not any(self.in_clan(account, clan) for account in accounts):  # one clan account = never ask again
            flow.ask_clan()
        elif flex_channel:
            flow.offer_flexing(flex_channel)
        else:
            await interaction.edit_original_response(content=intro)
            return
        await interaction.edit_original_response(content=flow.text(), view=flow)

    @app_commands.command(name="accounts", description="Shows the OSRS accounts linked to your Discord")
    async def accounts(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        accounts = await self.bot.db.get_osrs_accounts(interaction.user.id)
        if not accounts:
            await interaction.edit_original_response(content=lines.NO_ACCOUNTS)
            return
        await interaction.edit_original_response(embed=await self.accounts_embed(interaction.user, accounts))

    @app_commands.command(name="whois", description="Shows which OSRS accounts a server member plays")
    @app_commands.describe(member="The person to look up")
    async def whois(self, interaction: discord.Interaction, member: discord.Member) -> None:
        await interaction.response.defer()  # public: whois is a conversation piece
        accounts = await self.bot.db.get_osrs_accounts(member.id)
        if not accounts:
            await interaction.edit_original_response(
                content=lines.WHOIS_NOBODY.format(member=member.mention),
                allowed_mentions=discord.AllowedMentions.none(),  # show the name, but don't ping them
            )
            return
        await interaction.edit_original_response(embed=await self.accounts_embed(member, accounts))

    @app_commands.command(name="default", description="Picks which of your OSRS accounts is your main one")
    @app_commands.describe(rsn="One of your registered accounts")
    async def default(self, interaction: discord.Interaction, rsn: str) -> None:
        if await self.bot.db.set_default_osrs_account(interaction.user.id, rsn_key(rsn)):
            await interaction.response.send_message(
                lines.NEW_DEFAULT.format(rsn=discord.utils.escape_markdown(rsn)), ephemeral=True
            )
        else:
            await interaction.response.send_message(
                lines.NOT_YOURS.format(rsn=discord.utils.escape_markdown(rsn)), ephemeral=True
            )

    @app_commands.command(name="remove", description="Unlinks one of your OSRS accounts")
    @app_commands.describe(rsn="One of your registered accounts")
    async def remove(self, interaction: discord.Interaction, rsn: str) -> None:
        if await self.bot.db.remove_osrs_account(interaction.user.id, rsn_key(rsn)):
            await interaction.response.send_message(
                lines.REMOVED.format(rsn=discord.utils.escape_markdown(rsn)), ephemeral=True
            )
        else:
            await interaction.response.send_message(
                lines.NOT_YOURS.format(rsn=discord.utils.escape_markdown(rsn)), ephemeral=True
            )

    # Autocomplete: as you type the rsn for /osrs default or /osrs remove, Discord asks the bot for
    # suggestions, and we offer your own accounts. Stacking the two decorators hooks one function up to both.
    @default.autocomplete("rsn")
    @remove.autocomplete("rsn")
    async def your_accounts(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        accounts = await self.bot.db.get_osrs_accounts(interaction.user.id)
        typed = rsn_key(current)
        return [
            app_commands.Choice(name=account.rsn, value=account.rsn) for account in accounts if typed in account.rsn_key
        ][:25]  # Discord shows at most 25 suggestions

    @app_commands.command(name="flexing", description="Get what to paste into Dink to flex your drops")
    async def flexing(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)  # only you see it: the webhook link is a secret
        await interaction.edit_original_response(content=await self.flexing_kit_for(interaction.user.id))

    @app_commands.command(name="rotate-webhook", description="VIP: replace a leaked flexing webhook")
    @is_vip()
    async def rotate_webhook(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            main, deaths = flexing.flexing_channels(self.bot)
        except flexing.FlexingNotSetUp:
            await interaction.edit_original_response(content=lines.FLEX_NOT_SET_UP)
            return
        try:
            for channel in (main, deaths):
                if channel:
                    await flexing.replace_webhook(channel, self.bot.user)
        except discord.Forbidden:
            await interaction.edit_original_response(content=lines.FLEX_NO_PERMISSION.format(channel=main.mention))
            return
        logging.warning("Flexing webhook replaced by %s (ID: %s)", interaction.user.name, interaction.user.id)

        # Let everyone who had the old link know, a batch of mentions per message
        flexers = await self.bot.db.get_flexers()
        for start in range(0, len(flexers), MENTIONS_PER_MESSAGE):
            mentions = " ".join(f"<@{user_id}>" for user_id in flexers[start : start + MENTIONS_PER_MESSAGE])
            await main.send(lines.ROTATED_PING.format(mentions=mentions))
        await interaction.edit_original_response(
            content=lines.ROTATED_DONE.format(count=len(flexers), channel=main.mention)
        )


async def setup(bot):
    await bot.add_cog(Osrs(bot))
