import json
from pathlib import Path
import logging
import aiofiles


class BannedUsers:
    def __init__(self):
        root_dir = Path(__file__).resolve().parent.parent.parent
        self.data_dir = root_dir / "data" / "permissions"
        self.BANNED_USERS_FILE = self.data_dir / "banned_users_list.json"

        # Ensure the data directory and file exist
        self.data_dir.mkdir(exist_ok=True)
        if not self.BANNED_USERS_FILE.exists():
            logging.info("BANNED users file does not exist, creating a new one at %s", self.BANNED_USERS_FILE.name)
            self.BANNED_USERS_FILE.write_text(json.dumps([]))  # start with empty list

    # Load user IDs
    async def loadBannedUserIDs(self):
        """Loads banned user IDs from the JSON file."""

        async with aiofiles.open(self.BANNED_USERS_FILE, "r") as f:
            content = await f.read()
            return json.loads(content)

    async def saveBannedUserIDs(self, user_ids):
        """Saves banned user IDs to the JSON file."""

        async with aiofiles.open(self.BANNED_USERS_FILE, "w") as f:
            await f.write(json.dumps(user_ids, indent=2))

    async def addBannedUserID(self, user_id: int, ctx):
        """ Adds a banned user ID if not already present."""

        banned_user_ids = await self.loadBannedUserIDs()
        if user_id not in banned_user_ids:
            banned_user_ids.append(user_id)
            await self.saveBannedUserIDs(banned_user_ids)
            await ctx.response.send_message(f"User ID {user_id} has been banned from using the bot.")
            logging.info("Added BANNED user ID: %d", user_id)
        else:
            await ctx.response.send_message(f"User ID {user_id} is already banned from using the bot.")
            logging.info("User %d is already banned", user_id)

    async def removeBannedUserID(self, user_id: int, ctx):
        """Removes a banned user ID if present."""

        banned_user_ids = await self.loadBannedUserIDs()
        if user_id in banned_user_ids:
            banned_user_ids.remove(user_id)
            await self.saveBannedUserIDs(banned_user_ids)
            await ctx.response.send_message(f"User ID {user_id} has been unbanned from using the bot.")
            logging.info("Removed BANNED user ID: %d", user_id)
        else:
            await ctx.response.send_message(f"User ID {user_id} is not banned from using the bot.")
            logging.info("User %d is not banned", user_id)
