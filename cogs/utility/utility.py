import logging
import discord
from discord.ext.commands import Cog
from discord.app_commands import commands


class Utility(Cog, name="Utility"):
    """A cog that provides utility commands"""
    def __init__(self, bot):
        logging.info("Utility cog initialized.")
        self.bot = bot

    @commands.command(name='userinfo', description='Displays information about a user')
    async def userinfo(self, ctx, user: discord.User):
        """Displays information about a user"""
        embed = discord.Embed(
            title=f"User Info: {user.name}",
            description=f"Nickname: {user.display_name}\n"
                        f"ID: {user.id}\n"
                        f"Joined Discord: {user.created_at.strftime('%Y-%m-%d')}",
            color=discord.Colour.blue()
        )
        logging.info("User info requested for %s by %s", user.name, ctx.user.name)
        await ctx.response.send_message(embed=embed)

    @commands.command(name='serverinfo', description='Displays information about the server')
    async def serverinfo(self, ctx):
        """Displays information about the server"""
        guild = ctx.guild
        embed = discord.Embed(
            title=f"Server Info: {guild.name}", # name is still not working, fix later
            description=f"ID: {guild.id}\n"
                        f"Member Count: {guild.member_count}\n"
                        f"Created: {guild.created_at.strftime('%Y-%m-%d')}",
            color=discord.Colour.green()
        )
        logging.info("Server info requested by %s", ctx.user.name)
        await ctx.response.send_message(embed=embed)

async def setup(bot):
    """setup function required for loading the cog"""
    await bot.add_cog(Utility(bot))
    logging.info("Utility cog loaded.")
