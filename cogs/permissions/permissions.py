import logging
import discord
from discord.ext.commands import Cog
from discord.app_commands import commands
from .banned_users import BannedUsers
from .vip_users import VIPUsers


# TODO BEFORE MERGING
#   - make VIP & BANNED mutually exclusive
#   - update listing methods to return user names rather than ids
#   - ensure CRUD functionality for banned and VIP users is working before signoff

class Permissions(Cog, name="Permissions"):
    """A cog that provides permission-related commands"""

    def __init__(self, bot):
        logging.info("Permissions cog initialized.")
        self.bot = bot

    @commands.command(name='checkpermissions', description='Checks the permissions of a user')
    async def checkpermissions(self, ctx, user: discord.User):
        """Checks the permissions of a user"""
        logging.info("Permissions check requested for %s by %s", user.name, ctx.user.name)

        banned_users = BannedUsers()
        vip_users = VIPUsers()
        banned_list = await banned_users.loadBannedUserIDs()
        vip_list = await vip_users.loadVIPUserIDs()

        if user.id in banned_list:
            status = "BANNED"
            color = discord.Colour.red()
        elif user.id in vip_list:
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
    async def listbannedusers(self, ctx):
        """Lists all BANNED users"""
        logging.info("BANNED users list requested by %s", ctx.user.name)

        banned_users = BannedUsers()
        content = await banned_users.loadBannedUserIDs()

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

        banned_users = BannedUsers()
        await banned_users.addBannedUserID(user.id, ctx)

    @commands.command(name='listvipusers', description='Lists all VIP users')
    async def listvipusers(self, ctx):
        """Lists all VIP users"""
        logging.info("VIP users list requested by %s", ctx.user.name)

        vip_users = VIPUsers()
        content = await vip_users.loadVIPUserIDs()

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

        vip_users = VIPUsers()
        await vip_users.addVIPUserID(user.id, ctx)


async def setup(bot):
    """setup function required for loading the cog"""
    await bot.add_cog(Permissions(bot))
    logging.info("Permissions cog loaded.")
