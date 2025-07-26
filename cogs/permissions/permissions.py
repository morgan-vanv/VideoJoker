import logging
import discord
from discord import app_commands
from discord.ext.commands import Cog
from discord.app_commands import commands

from cogs.permissions.permissions_manager import PermissionManager


class Permissions(Cog, name="Permissions"):
    """A cog that provides permission-related commands"""

    def __init__(self, bot):
        logging.info("Permissions cog initialized.")
        self.bot = bot

    @app_commands.command(name='checkpermissions', description='Checks the permissions of a user')
    async def check_permissions(self, interaction: discord.Interaction, user: discord.User):
        """Checks the permissions of a user"""
        logging.info("Permissions check requested for %s by %s", user.name, interaction.user.name)
        await interaction.response.defer()

        try:
            permission_manager = PermissionManager()
            if await permission_manager.is_user_banned(user.id):
                status = "BANNED"
                color = discord.Colour.red()
            elif await permission_manager.is_user_vip(user.id):
                status = "VIP"
                color = discord.Colour.green()
            else:
                status = "No special permissions"
                color = discord.Colour.orange()

            embed = discord.Embed(
                title=f"Permissions for: {user.name}",
                description=f"Status: {status}",
                color=color
            )
            await interaction.followup.send(embed=embed)

        except Exception as e:
            logging.error("Error checking permissions for user %s: %s", user.name, str(e))
            await interaction.followup.send(f"An error occurred while checking permissions for {user.name}.", ephemeral=True)

    @app_commands.command(name='listbannedusers', description='Lists all banned users')
    async def list_banned_users(self, interaction: discord.Interaction):
        """Lists all BANNED users"""
        logging.info("BANNED users list requested by %s", interaction.user.name)
        await interaction.response.defer()

        try:
            content = await PermissionManager().read_banned_ids_from_file()
            embed = discord.Embed(
                title="BANNED Users",
                description=content,
                color=discord.Colour.red()
            )
            await interaction.followup.send(embed=embed)

        except Exception as e:
            logging.error("Error listing banned users: %s", str(e))
            await interaction.followup.send(f"An error occurred while listing banned users.", ephemeral=True)

    @app_commands.command(name='grantbanuser', description='Bans a user from using the bot')
    async def grant_ban_user(self, interaction: discord.Interaction, user: discord.User):
        """Grants BANNED status to a user"""
        logging.info("BANNED Status requested for %s by %s", user.name, interaction.user.name)
        await interaction.response.defer()

        try:
            permission_manager = PermissionManager()
            if not await permission_manager.is_user_vip(interaction.user.id):
                logging.warning("User %s attempted to grant BANNED status without being VIP themselves.", interaction.user.name)
                await interaction.followup.send("You must be a VIP user to grant BANNED status to others.", ephemeral=True)
            else:
                await permission_manager.add_banned_user_id(user, interaction)

        except Exception as e:
            logging.error("Error granting BANNED status to user %s: %s", user.name, str(e))
            await interaction.followup.send(f"An error occurred while granting BANNED status to {user.name}.", ephemeral=True)

    @app_commands.command(name='listvipusers', description='Lists all VIP users')
    async def list_vip_users(self, interaction: discord.Interaction):
        """Lists all VIP users"""
        logging.info("VIP users list requested by %s", interaction.user.name)
        await interaction.response.defer()

        try:
            content = await PermissionManager().read_vip_ids_from_file()
            embed = discord.Embed(
                title="VIP Users",
                description=content,
                color=discord.Colour.green()
            )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logging.error("Error listing VIP users: %s", str(e))
            await interaction.followup.send(f"An error occurred while listing VIP users.", ephemeral=True)

    @app_commands.command(name='grantvipuser', description='Grants VIP status to a user')
    async def grant_vip_user(self, interaction: discord.Interaction, user: discord.User):
        """Grants VIP status to a user"""
        logging.info("VIP Status requested for %s by %s", user.name, interaction.user.name)
        await interaction.response.defer()

        try:
            permission_manager = PermissionManager()
            if not await permission_manager.is_user_vip(interaction.user.id):
                logging.warning("User %s attempted to grant VIP status without being VIP themselves.", interaction.user.name)
                await interaction.followup.send("You must be a VIP user to grant VIP status to others.", ephemeral=True)
            else:
                await permission_manager.add_vip_user_id(user, interaction)

        except Exception as e:
            logging.error("Error granting VIP status to user %s: %s", user.name, str(e))
            await interaction.followup.send(f"An error occurred while granting VIP status to {user.name}.", ephemeral=True)

    @app_commands.command(name='resetpermissions', description='Resets permissions for a user')
    async def reset_permissions(self, interaction: discord.Interaction, user: discord.User):
        """Resets permissions for a user (removes from both VIP and BANNED lists)"""
        logging.info("Permissions reset requested for %s by %s", user.name, interaction.user.name)
        await interaction.response.defer()

        try:
            permission_manager = PermissionManager()
            if not await permission_manager.is_user_vip(interaction.user.id):
                logging.warning("User %s attempted to reset permissions without being VIP themselves.", interaction.user.name)
                await interaction.followup.send("You must be a VIP user to reset permissions for others.", ephemeral=True)
            else:
                await permission_manager.remove_vip_user_id(user.id)
                await permission_manager.remove_banned_user_id(user.id)
                await interaction.followup.send(f"Permissions for user {user.name} have been reset.")
                logging.info("Permissions reset for user: %s (ID: %d)", user.name, user.id)
        except Exception as e:
            logging.error("Error resetting permissions for user %s: %s", user.name, str(e))
            await interaction.followup.send(f"An error occurred while resetting permissions for {user.name}.", ephemeral=True)


async def setup(bot):
    """setup function required for loading the cog"""
    await bot.add_cog(Permissions(bot))
    logging.info("Permissions cog loaded.")
