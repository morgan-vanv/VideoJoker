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
            await db.execute('''
                CREATE TABLE IF NOT EXISTS economy (
                    user_id INTEGER PRIMARY KEY,
                    balance INTEGER DEFAULT 0
                )
            ''')
            await db.execute('''
                CREATE TABLE IF NOT EXISTS xp (
                    user_id INTEGER PRIMARY KEY,
                    server_xp INTEGER DEFAULT 0,
                    bot_xp INTEGER DEFAULT 0
                )
            ''')
            await db.execute('''
                CREATE TABLE IF NOT EXISTS reaction_roles (
                    message_id INTEGER,
                    emoji TEXT,
                    role_id INTEGER,
                    PRIMARY KEY (message_id, emoji)
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

    # Economy Methods
    async def get_balance(self, user_id: int) -> int:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT balance FROM economy WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0

    async def add_balance(self, user_id: int, amount: int):
        await self._execute("""
            INSERT INTO economy (user_id, balance) 
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET balance = balance + excluded.balance
        """, (user_id, amount))

    # XP Methods
    async def get_xp(self, user_id: int) -> tuple[int, int]:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT server_xp, bot_xp FROM xp WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                return row if row else (0, 0)

    async def add_server_xp(self, user_id: int, amount: int = 1):
        await self._execute("""
            INSERT INTO xp (user_id, server_xp, bot_xp) 
            VALUES (?, ?, 0)
            ON CONFLICT(user_id) DO UPDATE SET server_xp = server_xp + excluded.server_xp
        """, (user_id, amount))

    async def add_bot_xp(self, user_id: int, amount: int = 1):
        await self._execute("""
            INSERT INTO xp (user_id, server_xp, bot_xp) 
            VALUES (?, 0, ?)
            ON CONFLICT(user_id) DO UPDATE SET bot_xp = bot_xp + excluded.bot_xp
        """, (user_id, amount))

    # Reaction Role Methods
    async def add_reaction_role(self, message_id: int, emoji: str, role_id: int):
        await self._execute("""
            INSERT INTO reaction_roles (message_id, emoji, role_id) 
            VALUES (?, ?, ?)
            ON CONFLICT(message_id, emoji) DO UPDATE SET role_id = excluded.role_id
        """, (message_id, emoji, role_id))

    async def get_reaction_role(self, message_id: int, emoji: str) -> int:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT role_id FROM reaction_roles WHERE message_id = ? AND emoji = ?", (message_id, emoji)) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else None

