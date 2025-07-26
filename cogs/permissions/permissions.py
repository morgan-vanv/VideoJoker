import logging
import discord
from discord.ext.commands import Cog
from discord.app_commands import commands

from .permissions_manager import PermissionManager


# TODO BEFORE MERGING
#   - update listing methods to return user names rather than ids

class Permissions(Cog, name="Permissions"):
    """A cog that provides permission-related commands"""

    def __init__(self, bot):
        logging.info("Permissions cog initialized.")
        self.bot = bot

    @commands.command(name='checkpermissions', description='Checks the permissions of a user')
    async def check_permissions(self, ctx, user: discord.User):
        """Checks the permissions of a user"""
        logging.info("Permissions check requested for %s by %s", user.name, ctx.user.name)

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

        await ctx.response.send_message(embed=embed)

    @commands.command(name='listbannedusers', description='Lists all banned users')
    async def list_banned_users(self, ctx):
        """Lists all BANNED users"""
        logging.info("BANNED users list requested by %s", ctx.user.name)

        content = await PermissionManager().read_banned_ids_from_file()
        embed = discord.Embed(
            title="BANNED Users",
            description=content,
            color=discord.Colour.red()
        )
        await ctx.response.send_message(embed=embed)

    @commands.command(name='grantbanuser', description='Bans a user from using the bot')
    async def grant_ban_user(self, ctx, user: discord.User):
        """Grants BANNED status to a user"""
        logging.info("Grant BANNED Status requested for %s by %s", user.name, ctx.user.name)

        await PermissionManager().add_banned_user_id(user.id, ctx)

    @commands.command(name='listvipusers', description='Lists all VIP users')
    async def list_vip_users(self, ctx):
        """Lists all VIP users"""
        logging.info("VIP users list requested by %s", ctx.user.name)

        content = await PermissionManager().read_vip_ids_from_file()
        embed = discord.Embed(
            title="VIP Users",
            description=content,
            color=discord.Colour.green()
        )
        await ctx.response.send_message(embed=embed)

    @commands.command(name='grantvipuser', description='Grants VIP status to a user')
    async def grant_vip_user(self, ctx, user: discord.User):
        """Grants VIP status to a user"""
        logging.info("Grant VIP Status requested for %s by %s", user.name, ctx.user.name)

        await PermissionManager().add_vip_user_id(user.id, ctx)

    @commands.command(name='resetpermissions', description='Resets permissions for a user')
    async def reset_permissions(self, ctx, user: discord.User):
        """Resets permissions for a user (removes from both VIP and BANNED lists)"""
        logging.info("Reset permissions requested for %s by %s", user.name, ctx.user.name)

        permission_manager = PermissionManager()
        await permission_manager.remove_vip_user_id(user.id)
        await permission_manager.remove_banned_user_id(user.id)
        await ctx.response.send_message(f"Permissions for user ID {user.id} have been reset.")
        logging.info("Permissions reset for user ID: %d", user.id)


async def setup(bot):
    """setup function required for loading the cog"""
    await bot.add_cog(Permissions(bot))
    logging.info("Permissions cog loaded.")
