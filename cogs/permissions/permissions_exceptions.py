import discord


class ExecutingUserNotVIPError(Exception):
    """Exception thrown when a user lacks VIP status."""

    def __init__(self, user: discord.User):
        self.user = user
        self.msg = f"{user.name} (ID: {user.id}), you lack the VIP status required for this command"
        super().__init__(f"User {user.name} (ID: {user.id}) is not a VIP user.")


class ExecutingUserBannedError(Exception):
    """Exception thrown when a user is BANNED from the bot."""

    def __init__(self, user: discord.User):
        self.user = user
        self.msg = f"{user.name} (ID: {user.id}), you are banned from using the bot. Quit trying to use it!"
        super().__init__(f"User {user.name} (ID: {user.id}) is BANNED from using the bot.")
