import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext.commands import Cog

from cogs.ranks import ladder_of, rank_label
from core.database import USH_PER_MESSAGE
from ranks.ladder import rank_progress
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

    @app_commands.command(name='balance', description="Check your or another member's USh and their last payments.")
    async def balance(self, interaction: discord.Interaction, user: discord.User | None = None) -> None:
        target_user = user or interaction.user
        if target_user.bot:
            await interaction.response.send_message(lines.BALANCE_BOT, ephemeral=True)
            return

        balance = await self.bot.db.get_balance(target_user.id)
        moves = await self.bot.db.get_recent_ush_moves(target_user.id, limit=5)
        payments = "\n".join(lines.move_line(move, target_user.id) for move in moves) or lines.NO_PAYMENTS

        embed = discord.Embed(
            title=lines.BALANCE_TITLE.format(name=target_user.display_name),
            description=f"{lines.balance_line(balance)}\n{lines.USH_EXPLAINED}",
            color=discord.Colour.green(),
        )
        embed.add_field(name=lines.PAYMENTS_HEADING, value=f"{payments}\n\n{lines.PAY_HINT}", inline=False)
        # Discord wants a name on every field; "\u200b" is an invisible one (a zero-width space), for a plain line
        embed.add_field(name="\u200b", value=await self.standing_pointer(interaction.guild, target_user), inline=False)
        embed.set_footer(text=lines.EARNING)
        # Public, but looking someone up never pings them (and mentions inside an embed never ping anyway)
        await interaction.response.send_message(embed=embed, allowed_mentions=discord.AllowedMentions.none())

    async def standing_pointer(self, guild: Optional[discord.Guild], user: discord.abc.User) -> str:
        """📼 612 XP · @SWORN SWORDS · the full picture in /rank. The rank only on a server with a ladder."""
        xp = await self.bot.db.get_xp_totals(user.id)
        tiers = ladder_of(self.bot, guild)
        rank = None
        if tiers:
            member = guild.get_member(user.id)
            progress = rank_progress(tiers, xp.total, {role.id for role in member.roles} if member else set())
            if progress.tier is not None:
                rank = rank_label(guild, progress.tier)
        return lines.balance_pointer(xp.total, rank)

    @app_commands.command(name='pay', description='Send some of your USh to another member.')
    @app_commands.guild_only()
    @app_commands.describe(
        user="Who gets the USh",
        amount="How much to send",
        note="What it's for (optional, shows in both people's /balance)",
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

    @app_commands.command(name='gamble', description='Gamble your USh.')
    async def gamble(self, interaction: discord.Interaction, amount: int) -> None:

        # TODO: Implement actual gambling games
        await interaction.response.send_message(f"Stub: Gambled {amount} USh. Features coming soon!", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Economy(bot))
