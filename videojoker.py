""" This is the main file for the VideoJoker Discord bot. """

# standard imports
import sys
import os
import asyncio
import logging
from pathlib import Path

# third party imports
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

# Importing Cogs
from cogs.games import Games
from cogs.fun import Fun
from cogs.permissions.permissions_manager import PermissionManager
from cogs.utility import Utility
from cogs.permissions import Permissions
from shared.custom_exceptions import ExecutingUserNotVIPError


class VideoJoker(commands.Bot):
    """ The main bot class for VideoJoker, a Discord bot with various commands and functionalities. """

    def __init__(self):
        """ Initializes the VideoJoker bot with necessary intents and loads environment variables. """
        intents = discord.Intents.all()
        intents.message_content = True
        super().__init__(intents=intents, command_prefix="/")

        load_dotenv()
        self.token = os.getenv('DISCORD_TOKEN')
        self.permission_manager = PermissionManager()

    async def setup_hook(self):
        """Called when the bot is setting up (load cogs, sync commands, etc.)"""
        await self.add_cog(Games(self))
        await self.add_cog(Fun(self))
        await self.add_cog(Utility(self))
        await self.add_cog(Permissions(self))

        self.tree.on_error = self.on_app_command_error
        self.tree.interaction_check = self.global_interaction_check
        await self.tree.sync()
        logging.info("Commands synced")

    def restart_bot(self):
        """Restarts the bot by re-executing the current script."""
        os.execv(sys.executable, ['python'] + sys.argv)

    async def on_ready(self):
        """Called when the bot is ready to start working"""
        logging.info("%s is now running and ready to serve!", self.user)

    async def on_connect(self):
        """Called when the bot connects to Discord"""
        logging.info("%s has connected.", self.user)

    async def start_bot(self):
        """Starts the bot with the provided token."""
        await self.start(self.token)

    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Global error handler for all app_commands"""
        # left for debugging purposes, uncomment if needed to add more handled exceptions
        # logging.error("Error in command '%s': %s", interaction.command.name, repr(error))

        if isinstance(error.original, ExecutingUserNotVIPError):
            logging.warning("User %s (ID: %s) attempted to use a VIP-only command without VIP status.",
                            interaction.user.name, interaction.user.id)
            message = "🚫👑 You lack the VIP status required for this command."
        elif isinstance(error, app_commands.CommandOnCooldown):
            logging.warning("User %s (ID: %s) attempted to use command '%s' which is on cooldown.",
                            interaction.user.name, interaction.user.id, interaction.command.name)
            message = "⏳ This command is on cooldown. Try again later."
        else:
            logging.error("Unhandled/Unexpected error in command '%s': %s", interaction.command.name, repr(error),
                          exc_info=True)
            message = "❗ An unexpected error occurred. Please try again later."

        # Handling if the interaction has already been responded to
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)

    async def global_interaction_check(self, interaction: discord.Interaction) -> bool:
        """Global app command check to prevent banned users from using commands."""
        if await self.permission_manager.is_user_banned(interaction.user.id):
            logging.warning("Banned user %s (ID: %s) attempted to use a command.", interaction.user.name,
                            interaction.user.id)
            await interaction.response.send_message(
                "🚫 You are banned from using this bot.",
                ephemeral=True
            )
            return False
        return True


bot = VideoJoker()


# Beginning of the Root level commands exposed to users, the rest are imported from cogs above
@bot.tree.command()
async def ping(ctx):
    """A simple command to check if the bot is responsive."""
    logging.info('/ping command invoked by %s', ctx.user.name)
    await ctx.response.send_message('pong')


@bot.tree.command(name='listcommands', description='Shows list of all commands')
async def listcommands(ctx):
    """Displays a list of all available commands in the bot."""
    logging.info('/listcommands command invoked by %s', ctx.user.name)
    embed = discord.Embed(
        title="List of Commands",
        description="Here are all the available commands:",
        color=discord.Colour.dark_grey()
    )

    # Root-level commands
    embed.add_field(name="/ping", value="Returns pong", inline=False)
    embed.add_field(name="/listcommands", value="Shows list of all commands", inline=False)

    # Permissions cog commands
    embed.add_field(name="/checkpermissions", value="Checks the permissions of a user.", inline=False)
    embed.add_field(name="/listbannedusers", value="Lists all banned users.", inline=False)
    embed.add_field(name="/listvipusers", value="Lists all VIP users.", inline=False)
    embed.add_field(name="/grantbanuser", value="Bans a user from using the bot.", inline=False)
    embed.add_field(name="/grantvipuser", value="Grants VIP status to a user.", inline=False)
    embed.add_field(name="/resetpermissions", value="Resets permissions for a user.", inline=False)

    # Games cog commands
    embed.add_field(name="/coinflip", value="Flips a coin.", inline=False)
    embed.add_field(name="/diceroll", value="Rolls an N-sided die (defaults to 6).", inline=False)
    embed.add_field(name="/8ball", value="Ask the magic 8 ball a question.", inline=False)
    embed.add_field(name="/rockpaperscissors", value="Play rock-paper-scissors against the bot.", inline=False)

    # Fun cog commands
    embed.add_field(name="/say", value="Repeat after me.", inline=False)
    embed.add_field(name="/roast", value="Roast a user.", inline=False)

    # Utility cog commands
    embed.add_field(name="/userinfo", value="Displays information about a user.", inline=False)
    embed.add_field(name="/serverinfo", value="Displays information about the server.", inline=False)

    await ctx.response.send_message(embed=embed, ephemeral=False)


# Main entry point
if __name__ == "__main__":
    # creating necessary directories if they don't exist
    data_dir = Path(__file__).resolve().parent / "data"
    permissions_dir = data_dir / "permissions"
    logs_dir = data_dir / "logs"

    permissions_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    # set up logging
    logging.basicConfig(
        level=logging.INFO,  # Set logging level
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(f"{Path(__file__).resolve().parent / 'data' / 'logs' / 'bot.log'}",
                                mode='w',
                                encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    logging.getLogger("discord").setLevel(logging.WARNING)

    # running the bot
    load_dotenv()
    asyncio.run(bot.start_bot())

