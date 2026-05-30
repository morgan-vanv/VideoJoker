import logging
import discord
from discord import app_commands
from discord.ext.commands import Cog


class Utility(Cog, name="Utility"):
    """A cog that provides utility commands"""
    def __init__(self, bot):
        logging.info("Utility cog initialized.")
        self.bot = bot

    @app_commands.command(name='userinfo', description='Displays information about a user')
    async def userinfo(self, interaction: discord.Interaction, user: discord.User) -> None:
        """
        **Displays information about a user**

        :param interaction: The interaction object from discord
        :type interaction: discord.Interaction
        :param user: The Discord user to get information about.
        :type user: discord.User

        Usage Example: `/userinfo @SomeUser`
        """
        embed = discord.Embed(
            title=f"User Info: {user.name}",
            description=f"Nickname: {user.display_name}\n"
                        f"ID: {user.id}\n"
                        f"Joined Discord: {user.created_at.strftime('%Y-%m-%d')}",
            color=discord.Colour.blue()
        )
        logging.info("User info requested for %s by %s", user.name, interaction.user.name)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name='serverinfo', description='Displays information about the server')
    @app_commands.guild_only()
    async def serverinfo(self, interaction: discord.Interaction) -> None:
        """
        **Displays information about the server**

        :param interaction: The interaction object from discord
        :type interaction: discord.Interaction

        Usage Example: `/serverinfo`
        """
        guild = interaction.guild
        embed = discord.Embed(
            title=f"Server Info: {guild.name}",
            description=f"ID: {guild.id}\n"
                        f"Member Count: {guild.member_count}\n"
                        f"Created: {guild.created_at.strftime('%Y-%m-%d')}",
            color=discord.Colour.green()
        )
        logging.info("Server info requested by %s", interaction.user.name)
        await interaction.response.send_message(embed=embed)

