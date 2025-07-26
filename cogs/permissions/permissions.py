import logging
import discord
from discord import app_commands
from discord.ext.commands import Cog

from cogs.permissions.permissions_exceptions import ExecutingUserNotVIPError, ExecutingUserBannedError
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
            if await permission_manager.is_user_banned(interaction.user.id):
                raise ExecutingUserBannedError(interaction.user)

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

        except ExecutingUserBannedError as e:
            logging.warning("BANNED User %s attempted to check permissions.", interaction.user.name)
            await interaction.followup.send(e.msg, ephemeral=True)
        except Exception as e:
            logging.error("An Unexpected Error occurred while checking permissions for user %s: %s", user.name, str(e))
            await interaction.followup.send("An Unexpected Error occurred. Please try again", ephemeral=True)

    @app_commands.command(name='listbannedusers', description='Lists all banned users')
    async def list_banned_users(self, interaction: discord.Interaction):
        """Lists all BANNED users"""
        logging.info("BANNED users list requested by %s", interaction.user.name)
        await interaction.response.defer()

        try:
            permission_manager = PermissionManager()
            if await permission_manager.is_user_banned(interaction.user.id):
                raise ExecutingUserBannedError(interaction.user)

            content = await permission_manager.read_banned_ids_from_file()
            embed = discord.Embed(
                title="BANNED Users",
                description=content,
                color=discord.Colour.red()
            )
            await interaction.followup.send(embed=embed)

        except ExecutingUserBannedError as e:
            logging.warning("BANNED User %s attempted to list BANNED users.", interaction.user.name)
            await interaction.followup.send(e.msg, ephemeral=True)
        except Exception as e:
            logging.error("An Unexpected Error occurred while listing banned users: %s", str(e))
            await interaction.followup.send("An Unexpected Error occurred. Please try again", ephemeral=True)

    @app_commands.command(name='grantbanuser', description='Bans a user from using the bot')
    async def grant_ban_user(self, interaction: discord.Interaction, user: discord.User):
        """Grants BANNED status to a user"""
        logging.info("BANNED Status requested for %s by %s", user.name, interaction.user.name)
        await interaction.response.defer()

        try:
            permission_manager = PermissionManager()
            if await permission_manager.is_user_banned(interaction.user.id):
                raise ExecutingUserBannedError(interaction.user)
            if not await permission_manager.is_user_vip(interaction.user.id):
                raise ExecutingUserNotVIPError(interaction.user)

            await permission_manager.add_banned_user_id(user, interaction)

        except ExecutingUserBannedError as e:
            logging.warning("BANNED User %s attempted to grant BANNED Status.", interaction.user.name)
            await interaction.followup.send(e.msg, ephemeral=True)
        except ExecutingUserNotVIPError as e:
            logging.warning("Non-VIP User %s attempted to grant BANNED status.", interaction.user.name)
            await interaction.followup.send(e.msg, ephemeral=True)
        except Exception as e:
            logging.error("An Unexpected Error occurred while granting BANNED status to user %s: %s", user.name, str(e))
            await interaction.followup.send("An Unexpected Error occurred. Please try again", ephemeral=True)

    @app_commands.command(name='listvipusers', description='Lists all VIP users')
    async def list_vip_users(self, interaction: discord.Interaction):
        """Lists all VIP users"""
        logging.info("VIP users list requested by %s", interaction.user.name)
        await interaction.response.defer()

        try:
            permission_manager = PermissionManager()
            if await permission_manager.is_user_banned(interaction.user.id):
                raise ExecutingUserBannedError(interaction.user)

            content = await permission_manager.read_vip_ids_from_file()
            embed = discord.Embed(
                title="VIP Users",
                description=content,
                color=discord.Colour.green()
            )
            await interaction.followup.send(embed=embed)

        except ExecutingUserBannedError as e:
            logging.warning("BANNED User %s attempted to list VIP users.", interaction.user.name)
            await interaction.followup.send(e.msg, ephemeral=True)
        except Exception as e:
            logging.error("An Unexpected Error occurred while listing VIP users: %s", str(e))
            await interaction.followup.send("An Unexpected Error occurred. Please try again", ephemeral=True)

    @app_commands.command(name='grantvipuser', description='Grants VIP status to a user')
    async def grant_vip_user(self, interaction: discord.Interaction, user: discord.User):
        """Grants VIP status to a user"""
        logging.info("VIP Status requested for %s by %s", user.name, interaction.user.name)
        await interaction.response.defer()

        try:
            permission_manager = PermissionManager()
            if await permission_manager.is_user_banned(interaction.user.id):
                raise ExecutingUserBannedError(interaction.user)
            if not await permission_manager.is_user_vip(interaction.user.id):
                raise ExecutingUserNotVIPError(interaction.user)

            await permission_manager.add_vip_user_id(user, interaction)

        except ExecutingUserBannedError as e:
            logging.warning("BANNED User %s attempted to grant VIP Status.", interaction.user.name)
            await interaction.followup.send(e.msg, ephemeral=True)
        except ExecutingUserNotVIPError as e:
            logging.warning("Non-VIP User %s attempted to grant VIP status.", interaction.user.name)
            await interaction.followup.send(e.msg, ephemeral=True)
        except Exception as e:
            logging.error("An Unexpected Error occurred while granting VIP status to user %s: %s", user.name, str(e))
            await interaction.followup.send("An Unexpected Error occurred. Please try again", ephemeral=True)

    @app_commands.command(name='resetpermissions', description='Resets permissions for a user')
    async def reset_permissions(self, interaction: discord.Interaction, user: discord.User):
        """Resets permissions for a user (removes from both VIP and BANNED lists)"""
        logging.info("Permissions reset requested for %s by %s", user.name, interaction.user.name)
        await interaction.response.defer()

        try:
            permission_manager = PermissionManager()
            if await permission_manager.is_user_banned(interaction.user.id):
                raise ExecutingUserBannedError(interaction.user)
            if not await permission_manager.is_user_vip(interaction.user.id):
                raise ExecutingUserNotVIPError(interaction.user)

            await permission_manager.remove_vip_user_id(user.id)
            await permission_manager.remove_banned_user_id(user.id)
            await interaction.followup.send(f"Permissions for user {user.name} have been reset.")
            logging.info("Permissions reset for user: %s (ID: %d)", user.name, user.id)

        except ExecutingUserBannedError as e:
            logging.warning("BANNED User %s attempted to reset permissions.", interaction.user.name)
            await interaction.followup.send(e.msg, ephemeral=True)
        except ExecutingUserNotVIPError as e:
            logging.warning("Non-VIP User %s attempted to reset permissions", interaction.user.name)
            await interaction.followup.send(e.msg, ephemeral=True)
        except Exception as e:
            logging.error("An Unexpected Error occurred while resetting permissions for user %s: %s", user.name, str(e))
            await interaction.followup.send("An Unexpected Error occurred. Please try again", ephemeral=True)

