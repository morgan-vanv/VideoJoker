import logging
import discord
from discord.ext.commands import Cog
from discord.app_commands import commands
from .banned_users import BannedUsers
from .vip_users import VIPUsers

# TODO BEFORE MERGING
#   - move written files to data folder (banned & vip, as well as the bot_log.txt?)
#   - ensure CRUD functionality for banned and VIP users is working
#   - checkpermissions command needs to be implemented
#   - add user to vip or banned list commands need to be implemented

class Permissions(Cog, name="Permissions"):
    """A cog that provides permission-related commands"""
    def __init__(self, bot):
        logging.info("Permissions cog initialized.")
        self.bot = bot

    @commands.command(name='checkpermissions', description='Checks the permissions of a user')
    async def checkpermissions(self, ctx, user: discord.User):
        """Checks the permissions of a user"""
        # Placeholder implementation
        embed = discord.Embed(
            title=f"Permissions for: {user.name}",
            description="This command will display the user's permissions.",
            color=discord.Colour.orange()
        )
        logging.info("Permissions check requested for %s by %s", user.name, ctx.user.name)
        await ctx.response.send_message(embed=embed)

    @commands.command(name='grantpermission', description='Grants a specific permission to a user')
    async def grantpermission(self, ctx, user: discord.User, permission: str):
        """Grants a specific permission to a user"""
        # Placeholder implementation
        logging.info("Permission '%s' granted to %s by %s", permission, user.name, ctx.user.name)
        await ctx.response.send_message(f"Granted permission '{permission}' to {user.name}.")

    @commands.command(name='listbannedusers', description='Lists all banned users')
    async def listbannedusers(self, ctx):
        """Lists all banned users"""
        banned_users = BannedUsers()
        content = await banned_users.loadBannedUserIDs()

        embed = discord.Embed(
            title="Banned Users",
            description=content,
            color=discord.Colour.red()
        )
        logging.info("Banned users list requested by %s", ctx.user.name)
        await ctx.response.send_message(embed=embed)

    # @commands.command(name='botbanuser', description='Bans a user from using the bot')
    # async def bot_ban_user(self, ctx, user: discord.User):
    #     """Bans a user from using the bot"""
    #     banned_users = BannedUsers()
    #     await banned_users.addBannedUserID(user.id)
    #     logging.info("User %s has been banned by %s", user.name, ctx.user.name)
    #     await ctx.response.send_message(f"User {user.name} has been banned from using the bot.")

    @commands.command(name='listvipusers', description='Lists all VIP users')
    async def listvipusers(self, ctx):
        """Lists all VIP users"""
        vip_users = VIPUsers()
        content = await vip_users.loadVIPUserIDs()

        embed = discord.Embed(
            title="VIP Users",
            description=content,
            color=discord.Colour.green()
        )
        logging.info("Banned users list requested by %s", ctx.user.name)
        await ctx.response.send_message(embed=embed)

    # @commands.command(name='botvipuser', description='Grants VIP status to a user')
    # async def bot_vip_user(self, ctx, user: discord.User):
    #     """Grants VIP status to a user"""
    #     vip_users = VIPUsers()
    #     await vip_users.addBannedUserID(user.id)
    #     logging.info("User %s has been granted VIP status by %s", user.name, ctx.user.name)
    #     await ctx.response.send_message(f"User {user.name} has been granted VIP status.")

async def setup(bot):
    """setup function required for loading the cog"""
    await bot.add_cog(Permissions(bot))
    logging.info("Permissions cog loaded.")