import os
import aiosqlite
import logging
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "videojoker.db"

class Database:
    """
    Manages the SQLite database and provides an in-memory cache for user roles (VIP & BANNED).
    Roles are mutually exclusive.
    """

    def __init__(self):
        self.owner_id = int(os.getenv("OWNER", "0"))
        self.vips = set()
        self.banned = set()

    async def setup(self):
        """Initializes the database, creates the table, and loads the cache."""
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS user_roles (
                    user_id INTEGER PRIMARY KEY,
                    role TEXT CHECK(role IN ('VIP', 'BANNED'))
                )
            ''')
            # Drop the old permissions table if it exists to keep the schema clean
            await db.execute("DROP TABLE IF EXISTS permissions")
            await db.commit()
            
            # Load the cache
            async with db.execute("SELECT user_id, role FROM user_roles") as cursor:
                rows = await cursor.fetchall()
                for user_id, role in rows:
                    if role == 'VIP':
                        self.vips.add(user_id)
                    elif role == 'BANNED':
                        self.banned.add(user_id)

        # Owner is implicitly VIP
        self.vips.add(self.owner_id)
        logging.info("Database loaded. VIPs: %d, Banned: %d", len(self.vips), len(self.banned))

    async def _execute(self, query: str, parameters: tuple = ()):
        """Helper to execute a query securely using aiosqlite."""
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(query, parameters)
            await db.commit()

    async def set_user_role(self, user_id: int, role: str):
        """Sets a user's role to VIP or BANNED."""
        if role not in ('VIP', 'BANNED'):
            raise ValueError("Role must be 'VIP' or 'BANNED'")

        if user_id == self.owner_id and role == 'BANNED':
            raise ValueError("The bot owner cannot be banned.")

        await self._execute("""
            INSERT INTO user_roles (user_id, role) 
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET role = excluded.role
        """, (user_id, role))

        # Update cache
        if role == 'VIP':
            self.vips.add(user_id)
            self.banned.discard(user_id)
        elif role == 'BANNED':
            self.banned.add(user_id)
            self.vips.discard(user_id)

    async def remove_user_role(self, user_id: int):
        """Removes a user's role, reverting them to a normal user."""
        await self._execute("DELETE FROM user_roles WHERE user_id = ?", (user_id,))
        
        # Update cache
        if user_id != self.owner_id:
            self.vips.discard(user_id)
        self.banned.discard(user_id)
