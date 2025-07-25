import json
import os
from pathlib import Path
import logging
import aiofiles


class VIPUsers:
    """Manages VIP user IDs stored in a JSON file. Provides methods to load, save, add, and remove VIP user IDs."""

    def __init__(self):
        self.owner_id = int(os.getenv("OWNER", "0"))
        root_dir = Path(__file__).resolve().parent.parent.parent
        self.data_dir = root_dir / "data" / "permissions"
        self.VIP_USERS_FILE = self.data_dir / "vip_users_list.json"

        # Ensure the data directory and file exist
        self.data_dir.mkdir(exist_ok=True)
        if not self.VIP_USERS_FILE.exists():
            logging.info("VIP users file does not exist, creating a new one at %s", self.VIP_USERS_FILE.name)
            self.VIP_USERS_FILE.write_text(json.dumps([]))  # start with empty list

    async def load_vip_ids_from_file(self):
        """Loads VIP user IDs from the JSON file"""

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

    async def add_vip_user_id(self, user_id: int, ctx):
        """Adds a VIP user ID if not already present"""

        vip_user_ids = await self.load_vip_ids_from_file()
        if user_id not in vip_user_ids:
            vip_user_ids.append(user_id)
            await self.save_vip_ids_to_file(vip_user_ids)
            await ctx.response.send_message(f"User ID {user_id} has been granted VIP status.")
            logging.info("Added VIP user ID: %d", user_id)
        else:
            await ctx.response.send_message(f"User ID {user_id} is already a VIP user.")
            logging.info("User %d is already a VIP user", user_id)

    async def remove_vip_user_id(self, user_id: int, ctx):
        """Removes a VIP user ID if present"""

        vip_user_ids = await self.load_vip_ids_from_file()
        if user_id in vip_user_ids:
            vip_user_ids.remove(user_id)
            await self.save_vip_ids_to_file(vip_user_ids)
            await ctx.response.send_message(f"User ID {user_id} has been removed from VIP status.")
            logging.info("Removed VIP user ID: %d", user_id)
        else:
            await ctx.response.send_message(f"User ID {user_id} is not a VIP user.")
            logging.info("User ID %d not found in VIP users list", user_id)
