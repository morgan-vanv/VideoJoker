import os
import asyncio
import aiosqlite
import logging
from typing import NamedTuple, Optional
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "videojoker.db"


class OsrsAccount(NamedTuple):
    """One OSRS account linked to a Discord user (a row of osrs_accounts). A NamedTuple is a tuple whose
    parts have names, so code can say account.rsn instead of account[0]."""

    rsn: str  # the name as the player typed it, e.g. "Iron Morph"
    rsn_key: str  # the same name normalised for comparing, e.g. "iron morph" (see osrs/accounts.py)
    is_default: bool
    clan_answer: Optional[str]  # None (never asked), 'joining', 'member' or 'no'


class Database:
    """
    Manages the SQLite database and provides an in-memory cache for user roles (VIP & BANNED).
    Roles are mutually exclusive.
    """

    def __init__(self, db_path: Path = DB_PATH):
        # db_path defaults to the real database; tests pass a throwaway file instead
        self.db_path = db_path
        self.owner_id = int(os.getenv("OWNER", "0"))
        self.vips = set()
        self.banned = set()
        self.conn: Optional[aiosqlite.Connection] = None
        self.lock = asyncio.Lock()

    async def setup(self) -> None:
        """Initializes the database, creates the table, and loads the cache."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = await aiosqlite.connect(self.db_path)

        await self.conn.execute('''
            CREATE TABLE IF NOT EXISTS user_roles (
                user_id INTEGER PRIMARY KEY,
                role TEXT CHECK(role IN ('VIP', 'BANNED'))
            )
        ''')
        await self.conn.execute('''
            CREATE TABLE IF NOT EXISTS economy (
                user_id INTEGER PRIMARY KEY,
                balance INTEGER DEFAULT 0
            )
        ''')
        await self.conn.execute('''
            CREATE TABLE IF NOT EXISTS xp (
                user_id INTEGER PRIMARY KEY,
                server_xp INTEGER DEFAULT 0,
                bot_xp INTEGER DEFAULT 0
            )
        ''')
        await self.conn.execute('''
            CREATE TABLE IF NOT EXISTS reaction_roles (
                message_id INTEGER,
                emoji TEXT,
                role_id INTEGER,
                PRIMARY KEY (message_id, emoji)
            )
        ''')
        # OSRS accounts linked to Discord users (alts welcome). rsn_key is UNIQUE so two people can't
        # claim the same character. See docs/osrs-design.md.
        await self.conn.execute('''
            CREATE TABLE IF NOT EXISTS osrs_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                discord_id INTEGER NOT NULL,
                rsn TEXT NOT NULL,
                rsn_key TEXT NOT NULL UNIQUE,
                is_default INTEGER NOT NULL DEFAULT 0,
                clan_answer TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # Who has the flexing webhook, so they can be pinged when it's replaced
        await self.conn.execute('''
            CREATE TABLE IF NOT EXISTS osrs_flexers (
                discord_id INTEGER PRIMARY KEY,
                enrolled_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # Drop the old permissions table if it exists to keep the schema clean
        await self.conn.execute("DROP TABLE IF EXISTS permissions")
        await self.conn.commit()

        # Load the cache
        async with self.conn.execute("SELECT user_id, role FROM user_roles") as cursor:
            rows = await cursor.fetchall()
            for user_id, role in rows:
                if role == 'VIP':
                    self.vips.add(user_id)
                elif role == 'BANNED':
                    self.banned.add(user_id)

        # Owner is implicitly VIP (0 means OWNER isn't set, and 0 isn't a real user)
        if self.owner_id:
            self.vips.add(self.owner_id)
        logging.info("Database loaded. VIPs: %d, Banned: %d", len(self.vips), len(self.banned))

    async def close(self) -> None:
        """Closes the database connection."""
        if self.conn:
            await self.conn.close()

    async def _execute(self, query: str, parameters: tuple = ()) -> None:
        """Helper to execute a query securely using aiosqlite."""
        if self.conn is None:
            raise RuntimeError("Database connection is not initialized. Did you call setup()?")
        async with self.lock:
            try:
                await self.conn.execute(query, parameters)
                await self.conn.commit()
            except Exception as e:
                logging.error("Database execution error: %s | Query: %s | Params: %s", e, query, parameters)
                raise

    async def set_user_role(self, user_id: int, role: str) -> None:
        """Sets a user's role to VIP or BANNED."""
        if role not in ('VIP', 'BANNED'):
            raise ValueError("Role must be 'VIP' or 'BANNED'")

        if user_id == self.owner_id and role == 'BANNED':
            raise ValueError("The bot owner cannot be banned.")

        await self._execute(
            """
            INSERT INTO user_roles (user_id, role) 
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET role = excluded.role
        """,
            (user_id, role),
        )

        # Update cache
        if role == 'VIP':
            self.vips.add(user_id)
            self.banned.discard(user_id)
        elif role == 'BANNED':
            self.banned.add(user_id)
            self.vips.discard(user_id)

    async def remove_user_role(self, user_id: int) -> None:
        """Removes a user's role, reverting them to a normal user."""
        await self._execute("DELETE FROM user_roles WHERE user_id = ?", (user_id,))

        # Update cache
        if user_id != self.owner_id:
            self.vips.discard(user_id)
        self.banned.discard(user_id)

    # Economy Methods
    async def get_balance(self, user_id: int) -> int:
        if self.conn is None:
            raise RuntimeError("Database connection is not initialized. Did you call setup()?")
        async with self.lock:
            try:
                async with self.conn.execute("SELECT balance FROM economy WHERE user_id = ?", (user_id,)) as cursor:
                    row = await cursor.fetchone()
                    return row[0] if row else 0
            except Exception as e:
                logging.error("Database read error in get_balance for user %s: %s", user_id, e)
                raise

    async def add_balance(self, user_id: int, amount: int) -> None:
        await self._execute(
            """
            INSERT INTO economy (user_id, balance) 
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET balance = balance + excluded.balance
        """,
            (user_id, amount),
        )

    async def transfer_balance(self, sender_id: int, receiver_id: int, amount: int) -> bool:
        """Atomically transfers balance from sender to receiver. Returns True if successful."""
        if amount <= 0:
            return False  # a negative amount would move money backwards; /pay checks too, but the DB is the last line
        if self.conn is None:
            raise RuntimeError("Database connection is not initialized. Did you call setup()?")
        async with self.lock:
            try:
                # We use an atomic update where sender balance must be >= amount
                await self.conn.execute("BEGIN IMMEDIATE TRANSACTION")

                # Deduct from sender
                cursor = await self.conn.execute(
                    """
                    UPDATE economy 
                    SET balance = balance - ? 
                    WHERE user_id = ? AND balance >= ?
                """,
                    (amount, sender_id, amount),
                )

                if cursor.rowcount == 0:
                    await self.conn.rollback()
                    return False  # Insufficient funds or user not found

                # Add to receiver (insert if not exists)
                await self.conn.execute(
                    """
                    INSERT INTO economy (user_id, balance) 
                    VALUES (?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET balance = balance + excluded.balance
                """,
                    (receiver_id, amount),
                )

                await self.conn.commit()
                return True
            except Exception as e:
                try:
                    await self.conn.rollback()
                except Exception as rollback_err:
                    logging.error("Failed to rollback transaction: %s", rollback_err)
                logging.error("Database transfer error from %s to %s for %d: %s", sender_id, receiver_id, amount, e)
                return False

    # XP Methods
    async def get_xp(self, user_id: int) -> tuple[int, int]:
        if self.conn is None:
            raise RuntimeError("Database connection is not initialized. Did you call setup()?")
        async with self.lock:
            try:
                async with self.conn.execute(
                    "SELECT server_xp, bot_xp FROM xp WHERE user_id = ?", (user_id,)
                ) as cursor:
                    row = await cursor.fetchone()
                    return row if row else (0, 0)
            except Exception as e:
                logging.error("Database read error in get_xp for user %s: %s", user_id, e)
                raise

    async def add_server_xp(self, user_id: int, amount: int = 1) -> None:
        await self._execute(
            """
            INSERT INTO xp (user_id, server_xp, bot_xp) 
            VALUES (?, ?, 0)
            ON CONFLICT(user_id) DO UPDATE SET server_xp = server_xp + excluded.server_xp
        """,
            (user_id, amount),
        )

    async def add_bot_xp(self, user_id: int, amount: int = 1) -> None:
        await self._execute(
            """
            INSERT INTO xp (user_id, server_xp, bot_xp) 
            VALUES (?, 0, ?)
            ON CONFLICT(user_id) DO UPDATE SET bot_xp = bot_xp + excluded.bot_xp
        """,
            (user_id, amount),
        )

    # Reaction Role Methods
    async def add_reaction_role(self, message_id: int, emoji: str, role_id: int) -> None:
        await self._execute(
            """
            INSERT INTO reaction_roles (message_id, emoji, role_id) 
            VALUES (?, ?, ?)
            ON CONFLICT(message_id, emoji) DO UPDATE SET role_id = excluded.role_id
        """,
            (message_id, emoji, role_id),
        )

    async def get_reaction_role(self, message_id: int, emoji: str) -> Optional[int]:
        if self.conn is None:
            raise RuntimeError("Database connection is not initialized. Did you call setup()?")
        async with self.lock:
            try:
                async with self.conn.execute(
                    "SELECT role_id FROM reaction_roles WHERE message_id = ? AND emoji = ?", (message_id, emoji)
                ) as cursor:
                    row = await cursor.fetchone()
                    return row[0] if row else None
            except Exception as e:
                logging.error("Database read error in get_reaction_role: %s", e)
                raise

    # OSRS Methods (docs/osrs-design.md)
    async def _fetch_all(self, query: str, parameters: tuple = ()) -> list:
        """Helper for read queries: runs one SELECT and returns all its rows."""
        if self.conn is None:
            raise RuntimeError("Database connection is not initialized. Did you call setup()?")
        async with self.lock:
            try:
                async with self.conn.execute(query, parameters) as cursor:
                    return list(await cursor.fetchall())
            except Exception as e:
                logging.error("Database read error: %s | Query: %s | Params: %s", e, query, parameters)
                raise

    async def add_osrs_account(self, discord_id: int, rsn: str, rsn_key: str) -> Optional[int]:
        """Links an OSRS account to a Discord user. Their first account becomes their default.

        Returns None if it worked, or the Discord ID that already has this name (which can be the same
        person registering it twice).
        """
        if self.conn is None:
            raise RuntimeError("Database connection is not initialized. Did you call setup()?")
        # The check and the insert happen under one lock, so two people registering the same name at the
        # same moment can't both "win". (The UNIQUE on rsn_key would stop the second one anyway.)
        async with self.lock:
            try:
                async with self.conn.execute(
                    "SELECT discord_id FROM osrs_accounts WHERE rsn_key = ?", (rsn_key,)
                ) as cursor:
                    taken = await cursor.fetchone()
                if taken:
                    return taken[0]

                async with self.conn.execute(
                    "SELECT COUNT(*) FROM osrs_accounts WHERE discord_id = ?", (discord_id,)
                ) as cursor:
                    (account_count,) = await cursor.fetchone()

                await self.conn.execute(
                    "INSERT INTO osrs_accounts (discord_id, rsn, rsn_key, is_default) VALUES (?, ?, ?, ?)",
                    (discord_id, rsn, rsn_key, int(account_count == 0)),
                )
                await self.conn.commit()
                return None
            except Exception as e:
                await self.conn.rollback()
                logging.error("Database error in add_osrs_account for %s (%s): %s", discord_id, rsn, e)
                raise

    async def get_osrs_accounts(self, discord_id: int) -> list[OsrsAccount]:
        """A user's OSRS accounts: the default first, then in the order they were added."""
        rows = await self._fetch_all(
            """
            SELECT rsn, rsn_key, is_default, clan_answer FROM osrs_accounts
            WHERE discord_id = ? ORDER BY is_default DESC, id
        """,
            (discord_id,),
        )
        return [
            OsrsAccount(rsn, rsn_key, bool(is_default), clan_answer) for rsn, rsn_key, is_default, clan_answer in rows
        ]

    async def remove_osrs_account(self, discord_id: int, rsn_key: str) -> bool:
        """Unlinks one of a user's accounts. If it was their default, their oldest remaining account takes
        over. Returns False if they don't have an account with that name."""
        if self.conn is None:
            raise RuntimeError("Database connection is not initialized. Did you call setup()?")
        async with self.lock:
            try:
                cursor = await self.conn.execute(
                    "DELETE FROM osrs_accounts WHERE discord_id = ? AND rsn_key = ? RETURNING is_default",
                    (discord_id, rsn_key),
                )
                removed = await cursor.fetchone()
                await cursor.close()
                if removed is None:
                    return False
                if removed[0]:  # it was the default: promote the oldest one left (if any)
                    await self.conn.execute(
                        """
                        UPDATE osrs_accounts SET is_default = 1
                        WHERE id = (SELECT MIN(id) FROM osrs_accounts WHERE discord_id = ?)
                    """,
                        (discord_id,),
                    )
                await self.conn.commit()
                return True
            except Exception as e:
                await self.conn.rollback()
                logging.error("Database error in remove_osrs_account for %s (%s): %s", discord_id, rsn_key, e)
                raise

    async def set_default_osrs_account(self, discord_id: int, rsn_key: str) -> bool:
        """Makes one of a user's accounts their default. Returns False if they don't have it."""
        accounts = await self.get_osrs_accounts(discord_id)
        if rsn_key not in (account.rsn_key for account in accounts):
            return False
        # One UPDATE does both jobs: is_default becomes 1 for the chosen account and 0 for the others,
        # because (rsn_key = ?) is itself a true/false value in SQL.
        await self._execute(
            "UPDATE osrs_accounts SET is_default = (rsn_key = ?) WHERE discord_id = ?", (rsn_key, discord_id)
        )
        return True

    async def set_clan_answer(self, discord_id: int, rsn_key: str, answer: str) -> None:
        """Remembers what someone answered to "is this account joining the clan?"."""
        if answer not in ('joining', 'member', 'no'):
            raise ValueError("answer must be 'joining', 'member' or 'no'")
        await self._execute(
            "UPDATE osrs_accounts SET clan_answer = ? WHERE discord_id = ? AND rsn_key = ?",
            (answer, discord_id, rsn_key),
        )

    async def add_flexer(self, discord_id: int) -> None:
        """Remembers that this user has the flexing webhook (so they get pinged if it's ever replaced)."""
        await self._execute("INSERT OR IGNORE INTO osrs_flexers (discord_id) VALUES (?)", (discord_id,))

    async def is_flexer(self, discord_id: int) -> bool:
        rows = await self._fetch_all("SELECT 1 FROM osrs_flexers WHERE discord_id = ?", (discord_id,))
        return bool(rows)

    async def get_flexers(self) -> list[int]:
        rows = await self._fetch_all("SELECT discord_id FROM osrs_flexers ORDER BY enrolled_at")
        return [discord_id for (discord_id,) in rows]
