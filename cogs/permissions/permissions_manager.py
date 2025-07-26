import json
import os
from pathlib import Path
import logging
import aiofiles

class PermissionManager:
    """
    Manages user permissions, specifically BANNED and VIP statuses, storing in JSON files.
    This carries out the commands found in permissions.py
    """

    def __init__(self):
        self.owner_id = int(os.getenv("OWNER", "0"))
        root_dir = Path(__file__).resolve().parent.parent.parent
        self.data_dir = root_dir / "data" / "permissions"
        self.VIP_USERS_FILE = self.data_dir / "vip_users_list.json"
        self.BANNED_USERS_FILE = self.data_dir / "banned_users_list.json"

        # Ensure the data directory and files exist
        self.data_dir.mkdir(exist_ok=True)
        if not self.VIP_USERS_FILE.exists():
            logging.info("VIP users file does not exist, creating a new one at %s", self.VIP_USERS_FILE.name)
            self.VIP_USERS_FILE.write_text(json.dumps([]))
        if not self.BANNED_USERS_FILE.exists():
            logging.info("BANNED users file does not exist, creating a new one at %s", self.BANNED_USERS_FILE.name)
            self.BANNED_USERS_FILE.write_text(json.dumps([]))


    async def read_vip_ids_from_file(self):
        """Reads VIP user IDs from the JSON file"""

        async with aiofiles.open(self.VIP_USERS_FILE, "r") as f:
            content = await f.read()
            user_ids = json.loads(content)

        # Always include the owner ID
        if self.owner_id not in user_ids:
            user_ids.append(self.owner_id)

        return user_ids

    async def save_vip_ids_to_file(self, user_ids):
        """Saves VIP user IDs to the JSON file"""

        async with aiofiles.open(self.VIP_USERS_FILE, "w") as f:
            await f.write(json.dumps(user_ids, indent=2))

    async def is_user_vip(self, user_id: int) -> bool:
        """Checks if a user ID is in the VIP list"""

        vip_user_ids = await self.read_vip_ids_from_file()
        return user_id in vip_user_ids

    async def read_banned_ids_from_file(self):
        """Reads banned user IDs from the JSON file."""

        async with aiofiles.open(self.BANNED_USERS_FILE, "r") as f:
            content = await f.read()
            return json.loads(content)

    async def save_banned_ids_to_file(self, user_ids):
        """Saves banned user IDs to the JSON file."""

        async with aiofiles.open(self.BANNED_USERS_FILE, "w") as f:
            await f.write(json.dumps(user_ids, indent=2))

    async def is_user_banned(self, user_id: int) -> bool:
        """Checks if a user ID is in the banned list"""

        vip_user_ids = await self.read_banned_ids_from_file()
        return user_id in vip_user_ids

    async def add_vip_user_id(self, user_id: int, ctx):
        """Adds a VIP user ID if not already present or banned"""

        vip_users = await self.read_vip_ids_from_file()
        if self.is_user_banned(user_id):
            logging.info("Cannot add user ID %d to VIP as they are BANNED", user_id)
            await ctx.response.send_message(f"Cannot add user ID {user_id} to VIP as they are BANNED.")
        elif user_id in vip_users:
            logging.info("User ID %d is already a VIP user", user_id)
            await ctx.response.send_message(f"User ID {user_id} is already a VIP user.")
        else:
            vip_users.append(user_id)
            await self.save_vip_ids_to_file(vip_users)
            logging.info("Added VIP user ID to list: %d", user_id)
            await ctx.response.send_message(f"User ID {user_id} has been granted VIP status.")

    async def remove_vip_user_id(self, user_id: int):
        """Removes a VIP user ID if present"""

        vip_users = await self.read_vip_ids_from_file()
        if user_id in vip_users:
            vip_users.remove(user_id)
            await self.save_vip_ids_to_file(vip_users)
            logging.info("Removed VIP user ID from list: %d", user_id)
        else:
            logging.info("User ID %d is not a VIP user", user_id)

    async def add_banned_user_id(self, user_id: int, ctx):
        """Adds a banned user ID if not already present or banned"""

        banned_users = await self.read_banned_ids_from_file()
        if await self.is_user_vip(user_id):
            logging.info("Removing VIP status for %d before banning", user_id)
            await self.remove_vip_user_id(user_id)

        if user_id in banned_users:
            logging.info("User ID %d is already banned from the bot", user_id)
            await ctx.response.send_message(f"User ID {user_id} is already banned from the bot.")
        else:
            banned_users.append(user_id)
            await self.save_banned_ids_to_file(banned_users)
            logging.info("Added banned user ID to list: %d", user_id)
            await ctx.response.send_message(f"User ID {user_id} has been banned from the bot.")

    async def remove_banned_user_id(self, user_id: int):
        """Removes a banned user ID if present"""

        banned_users = await self.read_banned_ids_from_file()
        if user_id in banned_users:
            banned_users.remove(user_id)
            await self.save_banned_ids_to_file(banned_users)
            logging.info("Removed banned user ID from list: %d", user_id)
        else:
            logging.info("User ID %d is not banned from the bot", user_id)


