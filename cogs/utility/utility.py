import logging
import discord
from discord.ext.commands import Cog, command


# This cog provides utility commands.
class Utility(Cog, name="Utility"):
    def __init__(self, bot):
        logging.info("Utility cog initialized.")
        self.bot = bot

    @command(name='userinfo', description='Displays information about a user')
    async def userinfo(self, ctx, user: discord.User):
        """Displays information about a user"""
        embed = discord.Embed(
            title=f"User Info: {user.name}",
            description=f"ID: {user.id}\nJoined Discord: {user.created_at.strftime('%Y-%m-%d')}",
            color=discord.Colour.blue()
        )
        logging.info(f"User info requested for {user.name} by {ctx.author.name}")
        await ctx.send(embed=embed)

    @command(name='serverinfo', description='Displays information about the server')
    async def serverinfo(self, ctx):
        """Displays information about the server"""
        guild = ctx.guild
        embed = discord.Embed(
            title=f"Server Info: {guild.name}",
            description=f"ID: {guild.id}\nMember Count: {guild.member_count}\nCreated: {guild.created_at.strftime('%Y-%m-%d')}",
            color=discord.Colour.green()
        )
        logging.info(f"Server info requested by {ctx.author.name}")
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Utility(bot))
    logging.info("Utility cog loaded.")
