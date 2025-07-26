import discord


class ExecutingUserNotVIPError(Exception):
    """Exception thrown when the executing user lacks VIP status."""

    def __init__(self, user: discord.User):
        self.user = user
        self.msg = f"{user.name} (ID: {user.id}), you lack the VIP status required for this command"
        super().__init__(f"User {user.name} (ID: {user.id}) is not a VIP user.")


class ExecutingUserBannedError(Exception):
    """Exception thrown when the executing user is BANNED."""

    def __init__(self, user: discord.User):
        self.user = user
        self.msg = f"{user.name} (ID: {user.id}), you are banned from the bot."
        super().__init__(f"User {user.name} (ID: {user.id}) is banned from the bot.")

