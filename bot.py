import logging

import discord
from discord import app_commands
from discord.ext import commands

from cogs.permissions import is_vip, is_vip_command
from core.database import Database
from core.custom_exceptions import ExecutingUserNotVIPError
from core.version import get_version


class VideoJoker(commands.Bot):
    """The main bot class for VideoJoker, a Discord bot with various commands and functionalities."""

    def __init__(self, token: str):
        """Initializes the VideoJoker bot with necessary intents."""
        # Intents = which events Discord sends us. default() is everything except the three "privileged"
        # ones (members, presences, message content). XP and USh only need to know that a message was sent,
        # not what it says, so message content stays off.
        intents = discord.Intents.default()
        # members: the full member list, for /ladder tidy (and later welcome messages). Privileged, so it must
        # ALSO be switched on in the Developer Portal (Bot → Server Members Intent), or the bot can't log in.
        intents.members = True
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
            'cogs.ranks',
            'cogs.heartbeat',
            'cogs.osrs',
            'cogs.personal_vc',
            'cogs.guide',
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


def runnable_commands(tree: app_commands.CommandTree) -> list[app_commands.Command]:
    """Every command someone can actually run: the root ones (/ping), and the subcommands inside each group.
    A group like /ladder can't be run on its own, so walk_commands() opens it up: /ladder show, /ladder setup, ..."""
    found = []
    for cmd in tree.get_commands():
        if isinstance(cmd, app_commands.Group):
            found.extend(sub for sub in cmd.walk_commands() if isinstance(sub, app_commands.Command))
        else:
            found.append(cmd)
    return found


def setup_root_commands(bot: VideoJoker):
    @bot.tree.command(name='ping', description='Checks the bot is awake and shows which version is running.')
    # Only admins see /ping in the / menu, so it doesn't sit in front of /play for everyone else. Discord does the
    # hiding; the server owner can still hand it to other roles in Server Settings → Integrations → VideoJoker.
    @app_commands.default_permissions(administrator=True)
    async def ping(interaction: discord.Interaction) -> None:
        await interaction.response.send_message(f'pong · {get_version()}')

    def command_list_embeds(
        tree: app_commands.CommandTree, wanted, title: str, description: str
    ) -> list[discord.Embed]:
        """The list of commands for /listcommands and /listadmincommands, grouped by cog. wanted(cmd) says which
        commands go on it, so both lists come from the same code and can't drift apart."""

        # Group commands by Cog name or 'General'
        grouped_commands = {}
        for cmd in runnable_commands(tree):
            if not wanted(cmd):
                continue
            if hasattr(cmd, 'binding') and cmd.binding is not None:
                category = getattr(cmd.binding, 'qualified_name', 'General')
            else:
                category = 'General'

            if category not in grouped_commands:
                grouped_commands[category] = []
            grouped_commands[category].append(cmd)

        # Create embed
        embeds = [
            discord.Embed(
                title=title,
                description=description,
                color=discord.Colour.dark_grey(),
            )
        ]

        def add_field(name: str, value: str, inline: bool) -> None:
            # One embed holds at most 25 fields and 6000 characters in all. When the next field won't fit, carry on
            # in a fresh embed: one message can carry up to 10 of them.
            if len(embeds[-1].fields) == 25 or len(embeds[-1]) + len(name) + len(value) > 6000:
                embeds.append(discord.Embed(color=discord.Colour.dark_grey()))
            embeds[-1].add_field(name=name, value=value, inline=inline)

        # Sort categories so General comes first, then alphabetically
        sorted_categories = sorted(grouped_commands.keys(), key=lambda x: (x != 'General', x))

        for category in sorted_categories:
            category_commands = sorted(grouped_commands[category], key=lambda c: c.qualified_name)
            current_value = ""
            field_index = 1
            for cmd in category_commands:
                desc = cmd.description or "No description provided."
                line = f"**/{cmd.qualified_name}** - {desc}\n"

                # Check if adding this line would exceed the 1024 character limit for embed fields
                if len(current_value) + len(line) > 1000:
                    add_field(
                        name=f"{category} (Part {field_index})" if field_index > 1 else category,
                        value=current_value,
                        inline=False,
                    )
                    current_value = line
                    field_index += 1
                else:
                    current_value += line

            if current_value:
                add_field(
                    name=f"{category} (Part {field_index})" if field_index > 1 else category,
                    value=current_value,
                    inline=False,
                )

        return embeds

    @bot.tree.command(name='listcommands', description='Shows list of all commands')
    async def listcommands(interaction: discord.Interaction) -> None:
        # VIP-only commands are left out: only VIPs can run them, and they have /listadmincommands
        embeds = command_list_embeds(
            interaction.client.tree,
            lambda cmd: not is_vip_command(cmd),
            "List of Commands",
            "Here are all the available commands:",
        )
        await interaction.response.send_message(embeds=embeds, ephemeral=False)

    @bot.tree.command(name='listadmincommands', description='VIP: lists the commands only VIPs can use')
    @is_vip()
    async def listadmincommands(interaction: discord.Interaction) -> None:
        # Exactly the commands /listcommands leaves out. Only you see it: it's a VIP's cheat sheet.
        embeds = command_list_embeds(
            interaction.client.tree,
            is_vip_command,
            "List of VIP Commands",
            "These only work for VIPs:",
        )
        await interaction.response.send_message(embeds=embeds, ephemeral=True)
