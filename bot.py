import logging

import discord
from discord import app_commands
from discord.ext import commands

from core.database import Database
from core.custom_exceptions import ExecutingUserNotVIPError
from core.version import get_version


class VideoJoker(commands.Bot):
    """The main bot class for VideoJoker, a Discord bot with various commands and functionalities."""

    def __init__(self, token: str):
        """Initializes the VideoJoker bot with necessary intents."""
        # Intents = which events Discord sends us. default() is everything except the three "privileged"
        # ones (members, presences, message content), which this bot doesn't use: XP and USh only need to
        # know that a message was sent, not what it says. Enable one here (and in the Developer Portal)
        # when a feature needs it, e.g. intents.members = True for welcome messages.
        intents = discord.Intents.default()
        # Bot-wide default for who a message is allowed to ping. Commands that echo user text
        # (like /8ball) can't be used to ping @everyone or a role; @user mentions still work.
        # A single send can still override this by passing its own allowed_mentions (see /say).
        safe_mentions = discord.AllowedMentions(everyone=False, roles=False, users=True, replied_user=True)
        # Slash commands don't use a prefix, but commands.Bot still requires one. when_mentioned
        # (only "@VideoJoker ...") works without the message content intent.
        super().__init__(intents=intents, command_prefix=commands.when_mentioned, allowed_mentions=safe_mentions)

        self.token = token
        self.db = Database()
        # Set by main.py from DEV_GUILD_ID: when set, slash commands sync only to that test server
        self.dev_guild_id: int | None = None

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
            'cogs.reaction_roles',
        ]
        for extension in initial_extensions:
            await self.load_extension(extension)

        self.tree.on_error = self.on_app_command_error
        self.tree.interaction_check = self.global_interaction_check

        setup_root_commands(self)

        if self.dev_guild_id:
            # Dev bot: register commands in the test server only. Server commands update instantly,
            # while global ones (below) can take a while to appear and are rate-limited.
            dev_guild = discord.Object(id=self.dev_guild_id)
            self.tree.copy_global_to(guild=dev_guild)
            await self.tree.sync(guild=dev_guild)
            logging.info("Commands synced to dev server %s", self.dev_guild_id)
        else:
            await self.tree.sync()
            logging.info("Commands synced")

    async def on_ready(self):
        """Called when the bot is ready to start working"""
        logging.info("%s (%s) is now running and ready to serve!", self.user, get_version())

    async def on_connect(self):
        """Called when the bot connects to Discord"""
        logging.info("%s has connected.", self.user)

    async def start_bot(self):
        """Starts the bot with the provided token."""
        await self.start(self.token)

    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Global error handler for all app_commands"""
        # interaction.command is None when Discord sends a command the bot no longer has
        # (e.g. renamed or removed, but still synced in Discord), so never assume it exists.
        command_name = interaction.command.name if interaction.command else "unknown command"

        if isinstance(error, ExecutingUserNotVIPError):
            logging.warning(
                "User %s (ID: %s) attempted to use a VIP-only command without VIP status.",
                interaction.user.name,
                interaction.user.id,
            )
            message = "🚫👑 You lack the VIP status required for this command."
        elif isinstance(error, app_commands.CommandOnCooldown):
            logging.warning(
                "User %s (ID: %s) attempted to use command '%s' which is on cooldown.",
                interaction.user.name,
                interaction.user.id,
                command_name,
            )
            message = "⏳ This command is on cooldown. Try again later."
        else:
            # exc_info=error logs the error's own traceback (exc_info=True only works inside an except block)
            logging.error("Unhandled/Unexpected error in command '%s': %s", command_name, repr(error), exc_info=error)
            message = "❗ An unexpected error occurred. Please try again later."

        # Handling if the interaction has already been responded to
        try:
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except discord.HTTPException as send_error:
            # e.g. the interaction expired (3 s to respond, 15 min for followups): nothing left to reply to
            logging.warning("Could not send the error message for '%s': %s", command_name, send_error)

    async def global_interaction_check(self, interaction: discord.Interaction) -> bool:
        """Global app command check to prevent banned users from using commands."""
        # Log command usage
        if interaction.command:
            guild_name = interaction.guild.name if interaction.guild else "Direct Message"
            channel_name = interaction.channel.name if hasattr(interaction.channel, 'name') else "Unknown Channel"
            logging.info(
                "User %s (ID: %s) invoked /%s in Guild: '%s', Channel: '%s'",
                interaction.user.name,
                interaction.user.id,
                interaction.command.name,
                guild_name,
                channel_name,
            )

        if interaction.user.id in self.db.banned:
            logging.warning(
                "Banned user %s (ID: %s) attempted to use a command.", interaction.user.name, interaction.user.id
            )
            await interaction.response.send_message("🚫 You are banned from using this bot.", ephemeral=True)
            return False
        return True

    async def close(self):
        """Clean up resources before closing the bot."""
        logging.info("Closing database connection...")
        await self.db.close()
        await super().close()


def setup_root_commands(bot: VideoJoker):
    @bot.tree.command(name='ping', description='Checks the bot is awake and shows which version is running.')
    async def ping(interaction: discord.Interaction) -> None:
        await interaction.response.send_message(f'pong · {get_version()}')

    @bot.tree.command(name='listcommands', description='Shows list of all commands')
    async def listcommands(interaction: discord.Interaction) -> None:

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
            color=discord.Colour.dark_grey(),
        )

        # Sort categories so General comes first, then alphabetically
        sorted_categories = sorted(grouped_commands.keys(), key=lambda x: (x != 'General', x))

        for category in sorted_categories:
            category_commands = sorted(grouped_commands[category], key=lambda c: c.name)
            current_value = ""
            field_index = 1
            for cmd in category_commands:
                desc = cmd.description or "No description provided."
                line = f"**/{cmd.name}** - {desc}\n"

                # Check if adding this line would exceed the 1024 character limit for embed fields
                if len(current_value) + len(line) > 1000:
                    embed.add_field(
                        name=f"{category} (Part {field_index})" if field_index > 1 else category,
                        value=current_value,
                        inline=False,
                    )
                    current_value = line
                    field_index += 1
                else:
                    current_value += line

            if current_value:
                embed.add_field(
                    name=f"{category} (Part {field_index})" if field_index > 1 else category,
                    value=current_value,
                    inline=False,
                )

        await interaction.response.send_message(embed=embed, ephemeral=False)
