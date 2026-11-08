"""VideoJoker's real slash commands, built without connecting to Discord, for tests that need to know which
commands exist (the /help guard in test_guide.py, and the /listcommands split in test_listcommands.py).

How: make the bot object (making it doesn't log in), make each cog in cogs/, and put the cogs' commands on the bot's
command tree, the way bot.add_cog does. What we skip is everything that needs Discord or a database: no login, no
cog_load, no listeners. Then add the root commands from bot.py (/ping, /listcommands, /listadmincommands).
"""

import importlib
import pkgutil

from discord import app_commands
from discord.ext import commands

import cogs
from bot import VideoJoker, runnable_commands, setup_root_commands


def cog_classes() -> list[type[commands.Cog]]:
    """Every cog class in cogs/ (each file there is an extension the bot loads in setup_hook)."""
    found = []
    for module_info in pkgutil.iter_modules(cogs.__path__):
        module = importlib.import_module(f"cogs.{module_info.name}")
        for value in vars(module).values():
            # Only classes made in this file: `from discord.ext.commands import Cog` puts Cog itself here too
            if isinstance(value, type) and issubclass(value, commands.Cog) and value.__module__ == module.__name__:
                found.append(value)
    return found


def build_bot() -> VideoJoker:
    """A bot whose command tree holds every real command. Call it from an async test: some cogs make their
    buttons when they're created, and discord.py's buttons need a running event loop."""
    bot = VideoJoker(token="not-a-real-token")
    for cog_class in cog_classes():
        cog = cog_class(bot)
        # Same as bot.add_cog: a GroupCog is one group of subcommands (/ladder ...), any other cog adds its
        # commands one by one
        if cog.app_command is not None:
            bot.tree.add_command(cog.app_command)
        else:
            for command in cog.get_app_commands():
                bot.tree.add_command(command)
    setup_root_commands(bot)
    return bot


def commands_by_name(bot: VideoJoker) -> dict[str, app_commands.Command]:
    """Every command someone can run, by its full name: "ping", "ladder show", "osrs register", ... (the same
    commands /listcommands goes through, from bot.py's runnable_commands, as a dictionary)."""
    return {command.qualified_name: command for command in runnable_commands(bot.tree)}
