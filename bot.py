import sys
import os
import logging

import discord
from discord import app_commands
from discord.ext import commands

from core.database import Database
from core.custom_exceptions import ExecutingUserNotVIPError

class VideoJoker(commands.Bot):
    """ The main bot class for VideoJoker, a Discord bot with various commands and functionalities. """

    def __init__(self, token: str):
        """ Initializes the VideoJoker bot with necessary intents. """
        intents = discord.Intents.all()
        intents.message_content = True
        super().__init__(intents=intents, command_prefix="/")
        
        self.token = token
        self.db = Database()

    async def setup_hook(self):
        """Called when the bot is setting up (load cogs, sync commands, etc.)"""
        await self.db.setup()
        
        initial_extensions = [
            'cogs.games', 
            'cogs.fun', 
            'cogs.utility', 
            'cogs.permissions', 
            'cogs.music',
            'cogs.economy',
            'cogs.reaction_roles'
        ]
        for extension in initial_extensions:
            await self.load_extension(extension)

        self.tree.on_error = self.on_app_command_error
        self.tree.interaction_check = self.global_interaction_check
        
        setup_root_commands(self)
        
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
        if isinstance(error, ExecutingUserNotVIPError):
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
        if interaction.user.id in self.db.banned:
            logging.warning("Banned user %s (ID: %s) attempted to use a command.", interaction.user.name,
                            interaction.user.id)
            await interaction.response.send_message(
                "🚫 You are banned from using this bot.",
                ephemeral=True
            )
            return False
        return True


def setup_root_commands(bot: VideoJoker):
    @bot.tree.command(name='ping', description='A simple command to check if the bot is responsive.')
    async def ping(interaction: discord.Interaction) -> None:
        logging.info('/ping command invoked by %s', interaction.user.name)
        await interaction.response.send_message('pong')

    @bot.tree.command(name='listcommands', description='Shows list of all commands')
    async def listcommands(interaction: discord.Interaction) -> None:
        logging.info('/listcommands command invoked by %s', interaction.user.name)
        
        # Get all global commands registered in the tree
        all_commands = interaction.client.tree.get_commands()
        
        # Group commands by Cog name or 'General'
        grouped_commands = {}
        for cmd in all_commands:
            if hasattr(cmd, 'binding') and cmd.binding is not None:
                category = getattr(cmd.binding, 'qualified_name', 'General')
            else:
                category = 'General'
            
            if category not in grouped_commands:
                grouped_commands[category] = []
            grouped_commands[category].append(cmd)
            
        # Create embed
        embed = discord.Embed(
            title="List of Commands",
            description="Here are all the available commands:",
            color=discord.Colour.dark_grey()
        )
        
        # Sort categories so General comes first, then alphabetically
        sorted_categories = sorted(grouped_commands.keys(), key=lambda x: (x != 'General', x))
        
        for category in sorted_categories:
            category_commands = sorted(grouped_commands[category], key=lambda c: c.name)
            command_list = []
            for cmd in category_commands:
                desc = cmd.description or "No description provided."
                command_list.append(f"**/{cmd.name}** - {desc}")
            
            embed.add_field(
                name=category,
                value="\n".join(command_list) if command_list else "No commands.",
                inline=False
            )
            
        await interaction.response.send_message(embed=embed, ephemeral=False)
