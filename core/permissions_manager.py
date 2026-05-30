import os
import logging
import discord
from shared.database import get_db

class PermissionManager:
    """
    **Manages user permissions, specifically BANNED and VIP statuses, storing in an SQLite database.**
    """

    def __init__(self):
        self.owner_id = int(os.getenv("OWNER", "0"))

    async def get_all_vips(self) -> list[int]:
        """Returns a list of all VIP user IDs, ensuring the owner is included."""
        async with get_db() as db:
            async with db.execute("SELECT user_id FROM permissions WHERE is_vip = 1") as cursor:
                rows = await cursor.fetchall()
                vips = [row[0] for row in rows]
                if self.owner_id not in vips:
                    vips.append(self.owner_id)
                return vips

    async def get_all_banned(self) -> list[int]:
        """Returns a list of all banned user IDs."""
        async with get_db() as db:
            async with db.execute("SELECT user_id FROM permissions WHERE is_banned = 1") as cursor:
                rows = await cursor.fetchall()
                return [row[0] for row in rows]

    async def is_user_vip(self, user_id: int) -> bool:
        if user_id == self.owner_id:
            return True
        async with get_db() as db:
            async with db.execute("SELECT is_vip FROM permissions WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                return bool(row[0]) if row else False

    async def is_user_banned(self, user_id: int) -> bool:
        async with get_db() as db:
            async with db.execute("SELECT is_banned FROM permissions WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                return bool(row[0]) if row else False

    async def add_vip_user_id(self, user: discord.User, interaction: discord.Interaction) -> None:
        if await self.is_user_banned(user.id):
            logging.info("Cannot add user ID %d to VIP as they are BANNED", user.id)
            await interaction.followup.send(f"Cannot give user {user.name} VIP status, as they are BANNED.")
            return

        if await self.is_user_vip(user.id):
            logging.info("User ID %d is already a VIP user", user.id)
            await interaction.followup.send(f"User {user.name} already has VIP status.")
            return

        async with get_db() as db:
            await db.execute("""
                INSERT INTO permissions (user_id, is_vip, is_banned) 
                VALUES (?, 1, 0)
                ON CONFLICT(user_id) DO UPDATE SET is_vip = 1
            """, (user.id,))
            await db.commit()

        logging.info("Added VIP user ID to list: %d", user.id)
        await interaction.followup.send(f"User {user.name} has been granted VIP status.")

    async def add_banned_user_id(self, user: discord.User, interaction: discord.Interaction) -> None:
        if await self.is_user_vip(user.id):
            logging.info("Removing VIP status for %d before banning...", user.id)
            await self.remove_vip_user_id(user.id)

        if await self.is_user_banned(user.id):
            logging.info("User ID %d is already banned from the bot", user.id)
            await interaction.followup.send(f"User {user.name} is already banned from the bot.")
            return

        async with get_db() as db:
            await db.execute("""
                INSERT INTO permissions (user_id, is_vip, is_banned) 
                VALUES (?, 0, 1)
                ON CONFLICT(user_id) DO UPDATE SET is_banned = 1, is_vip = 0
            """, (user.id,))
            await db.commit()

        logging.info("Added banned user ID to list: %d", user.id)
        await interaction.followup.send(f"User {user.name} has been banned from the bot.")

    async def remove_vip_user_id(self, user_id: int) -> None:
        async with get_db() as db:
            await db.execute("UPDATE permissions SET is_vip = 0 WHERE user_id = ?", (user_id,))
            await db.commit()
        logging.info("Removed VIP status for user ID: %d", user_id)

    async def remove_banned_user_id(self, user_id: int) -> None:
        async with get_db() as db:
            await db.execute("UPDATE permissions SET is_banned = 0 WHERE user_id = ?", (user_id,))
            await db.commit()
        logging.info("Removed Banned status for user ID: %d", user_id)
