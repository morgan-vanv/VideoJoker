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
        await interaction.response.send_message(embed=embed)

    @Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is None:
            return
        # Add 1 Server XP for every message
        await self.bot.db.add_server_xp(message.author.id, 1)

    @Cog.listener()
    async def on_app_command_completion(self, interaction: discord.Interaction, _command: discord.app_commands.Command | discord.app_commands.ContextMenu):
        # Add 1 Bot XP for every completed command
        if interaction.user.bot:
            return
        await self.bot.db.add_bot_xp(interaction.user.id, 1)

    @app_commands.command(name='rank', description="Check your or another user's XP rank.")
    async def rank(self, interaction: discord.Interaction, user: discord.User = None) -> None:
        target_user = user or interaction.user
        server_xp, bot_xp = await self.bot.db.get_xp(target_user.id)
        
        embed = discord.Embed(
            title=f"Engagement Rank: {target_user.name}",
            description=f"**Server Engagement (Messages):** {server_xp} XP\n"
                        f"**Bot Engagement (Commands):** {bot_xp} XP",
            color=discord.Colour.purple()
        )
        await interaction.response.send_message(embed=embed, ephemeral=False)

    @app_commands.command(name='leaderboard', description='Shows the top users in server or bot engagement.')
    @app_commands.choices(category=[
        app_commands.Choice(name='Server Engagement', value='server_xp'),
        app_commands.Choice(name='Bot Engagement', value='bot_xp')
    ])
    async def leaderboard(self, interaction: discord.Interaction, category: app_commands.Choice[str]) -> None:
        # TODO: Implement database query for top 10 and display leaderboard
        await interaction.response.send_message(f"Stub: Leaderboard for '{category.name}'", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Utility(bot))
