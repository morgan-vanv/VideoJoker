import json
import os
from pathlib import Path
import logging
import aiofiles
import asyncio

class BannedUsers:
    def __init__(self):
        # Get root directory of script
        root_dir = Path(__file__).resolve().parent
        self.BANNED_USERS_FILE = root_dir / "banned_users_list.json"
        # Ensure file exists
        if not self.BANNED_USERS_FILE.exists():
            self.BANNED_USERS_FILE.write_text(json.dumps([]))  # start with empty list

    # Load user IDs
    async def loadBannedUserIDs(self):
        async with aiofiles.open(self.BANNED_USERS_FILE, "r") as f:
            content = await f.read()
            return json.loads(content)

    # Save user IDs
    async def saveBannedUserIDs(self, user_ids):
        async with aiofiles.open(self.BANNED_USERS_FILE, "w") as f:
            await f.write(json.dumps(user_ids, indent=2))

    # Add user ID if not already present
    async def addBannedUserID(self, user_id: int):
        user_ids = await self.loadBannedUserIDs()
        if user_id not in user_ids:
            user_ids.append(user_id)
            await self.saveBannedUserIDs(user_ids)

    # Remove user ID if present
    async def removeBannedUserID(self, user_id: int):
        user_ids = await self.loadBannedUserIDs()
        if user_id in user_ids:
            user_ids.remove(user_id)
            await self.saveBannedUserIDs(user_ids)