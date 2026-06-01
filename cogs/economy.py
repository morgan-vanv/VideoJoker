import logging
import discord
from discord import app_commands
from discord.ext import commands
from discord.ext.commands import Cog

class Economy(Cog, name="Economy"):
    """A cog that provides economy commands"""
    def __init__(self, bot):
        logging.info("Economy cog initialized.")
        self.bot = bot

    @Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        
        # Add 1 USh for every message
        await self.bot.db.add_balance(message.author.id, 1)

    @app_commands.command(name='balance', description="Check your or another user's balance.")
    async def balance(self, interaction: discord.Interaction, user: discord.User = None) -> None:
        target_user = user or interaction.user
        balance = await self.bot.db.get_balance(target_user.id)
        await interaction.response.send_message(f"{target_user.mention} has {balance} USh.", ephemeral=False)

    @app_commands.command(name='pay', description='Send USh to another user.')
    async def pay(self, interaction: discord.Interaction, user: discord.User, amount: int) -> None:
        if amount <= 0:
            await interaction.response.send_message("Amount must be greater than 0.", ephemeral=True)
            return
        
        sender_balance = await self.bot.db.get_balance(interaction.user.id)
        if sender_balance < amount:
            await interaction.response.send_message("You don't have enough USh.", ephemeral=True)
            return

        await self.bot.db.add_balance(interaction.user.id, -amount)
        await self.bot.db.add_balance(user.id, amount)
        await interaction.response.send_message(f"Successfully sent {amount} USh to {user.mention}.", ephemeral=False)

    @app_commands.command(name='gamble', description='Gamble your USh.')
    async def gamble(self, interaction: discord.Interaction, amount: int) -> None:
        # TODO: Implement actual gambling games
        await interaction.response.send_message(f"Stub: Gambled {amount} USh. Features coming soon!", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Economy(bot))
