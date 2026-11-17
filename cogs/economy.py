import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext.commands import Cog

from core.database import USH_PER_MESSAGE
from standing import lines

# The most one /pay can send (a typo guard: nobody means to send 10 million by accident)
MAX_PAYMENT = 1_000_000


class Economy(Cog, name="Economy"):
    """A cog that provides economy commands"""

    def __init__(self, bot):
        logging.info("Economy cog initialized.")
        self.bot = bot

    @Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is None:
            return

        # Every message earns USh (USH_PER_MESSAGE in core/database.py, so the help text and the payout match).
        # Not written to the ledger: that's for real payments, one row per message would bury them.
        await self.bot.db.add_balance(message.author.id, USH_PER_MESSAGE)

    @app_commands.command(name='pay', description='Send some of your USh to another member.')
    @app_commands.guild_only()
    @app_commands.describe(
        user="Who gets the USh",
        amount="How much to send",
        note="What it's for (optional, shows in both people's /profile)",
    )
    async def pay(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        # Range makes Discord itself refuse 0, negatives and silly amounts before the command even runs
        amount: app_commands.Range[int, 1, MAX_PAYMENT],
        note: Optional[app_commands.Range[str, 1, 100]] = None,
    ) -> None:
        if user.id == interaction.user.id:
            await interaction.response.send_message(lines.PAY_SELF, ephemeral=True)
            return
        if user.bot:
            await interaction.response.send_message(lines.PAY_BOT, ephemeral=True)
            return

        success = await self.bot.db.transfer_balance(
            interaction.user.id, user.id, amount, note=note, guild_id=interaction.guild.id
        )
        if not success:
            balance = await self.bot.db.get_balance(interaction.user.id)
            if balance >= amount:
                # They had the money, so it was the database that failed (the log has the details)
                await interaction.response.send_message(lines.PAY_JAMMED, ephemeral=True)
            else:
                await interaction.response.send_message(
                    lines.PAY_SHORT.format(balance=f"{balance:,}", amount=f"{amount:,}"), ephemeral=True
                )
            return

        logging.info("/pay: %s sent %s USh to %s", interaction.user.id, amount, user.id)
        # Ping the person who got paid (they'd want to know), and nobody else: users=[user] means even a note
        # with someone else's @mention in it can't ping them
        await interaction.response.send_message(
            lines.pay_done(interaction.user.mention, user.mention, amount, note),
            allowed_mentions=discord.AllowedMentions(everyone=False, roles=False, users=[user]),
        )

    # /gamble is a stub (starter work for the crew), so it stays out of the / menu until it does something
    # (Morgan, 2026-11-16: no placeholders in the menu). To bring it back, put this decorator back on:
    # @app_commands.command(name='gamble', description='Gamble your USh.')
    async def gamble(self, interaction: discord.Interaction, amount: int) -> None:

        # TODO: Implement actual gambling games
        await interaction.response.send_message(f"Stub: Gambled {amount} USh. Features coming soon!", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Economy(bot))
