import discord
from discord import app_commands

class ExecutingUserNotVIPError(app_commands.CheckFailure):
    """Exception thrown when the executing user lacks VIP status."""

    def __init__(self, user: discord.User):
        self.user = user
        self.msg = f"{user.name} (ID: {user.id}), you lack the VIP status required for this command"
        super().__init__(self.msg)

class ExecutingUserBannedError(app_commands.CheckFailure):
    """Exception thrown when the executing user is BANNED."""

    def __init__(self, user: discord.User):
        self.user = user
        self.msg = f"{user.name} (ID: {user.id}), you are banned from the bot."
        super().__init__(self.msg)
