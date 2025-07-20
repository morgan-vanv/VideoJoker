import json
import os
from pathlib import Path
import logging
import aiofiles
import asyncio
from dotenv import load_dotenv

class VIPUsers:
    def __init__(self):
        self.owner_id = int(os.getenv("OWNER", "0"))
        root_dir = Path(__file__).resolve().parent.parent.parent
        self.data_dir = root_dir / "data" / "permissions"
        self.VIP_USERS_FILE = self.data_dir / "vip_users_list.json"

        # Ensure the data directory and file exist
        self.data_dir.mkdir(exist_ok=True)
        if not self.VIP_USERS_FILE.exists():
            self.BANNED_USERS_FILE.write_text(json.dumps([]))  # start with empty list

    # Load user IDs
    async def loadVIPUserIDs(self):
        async with aiofiles.open(self.VIP_USERS_FILE, "r") as f:
            content = await f.read()
            user_ids = json.loads(content)

        # Always include the owner ID
        if self.owner_id not in user_ids:
            user_ids.append(self.owner_id)

        return user_ids

    # Save user IDs
    async def saveVIPUserIDs(self, user_ids):
        async with aiofiles.open(self.VIP_USERS_FILE, "w") as f:
            await f.write(json.dumps(user_ids, indent=2))

    # Add user ID if not already present
    async def addVIPUserID(self, user_id: int):
        user_ids = await self.loadVIPUserIDs()
        if user_id not in user_ids:
            user_ids.append(user_id)
            await self.saveVIPUserIDs(user_ids)

    # Remove user ID if present
    async def removeVIPUserID(self, user_id: int):
        user_ids = await self.loadVIPUserIDs()
        if user_id in user_ids:
            user_ids.remove(user_id)
            await self.saveVIPUserIDs(user_ids)