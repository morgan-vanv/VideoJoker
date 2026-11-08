import os
import asyncio
import aiosqlite
import logging
from typing import NamedTuple, Optional
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "videojoker.db"

# One XP number for everything: 1 per message, 5 per slash command, plus any bonus (e.g. /ladder tidy topping up
# Pancake-era ranks). The xp table keeps the raw counts (server_xp = messages, bot_xp = commands), and the total
# is worked out from them, so the columns never change meaning (a rollback runs old code on this database).
XP_PER_MESSAGE = 1
XP_PER_COMMAND = 5
TOTAL_XP_SQL = f"server_xp * {XP_PER_MESSAGE} + bot_xp * {XP_PER_COMMAND} + bonus_xp"


class OsrsAccount(NamedTuple):
    """One OSRS account linked to a Discord user (a row of osrs_accounts). A NamedTuple is a tuple whose
    parts have names, so code can say account.rsn instead of account[0]."""

    rsn: str  # the name as the player typed it, e.g. "Iron Morph"
    rsn_key: str  # the same name normalised for comparing, e.g. "iron morph" (see osrs/accounts.py)
    is_default: bool
    clan_answer: Optional[str]  # None (never asked), 'joining', 'member' or 'no'


class XpTotals(NamedTuple):
    """Someone's XP and where it came from."""

    messages: int  # server_xp: messages sent (1 XP each)
    commands: int  # bot_xp: slash commands run (5 XP each)
    bonus: int  # bonus_xp: given, not earned (e.g. /ladder tidy topping up an old rank)
    total: int


class RankTierRow(NamedTuple):
    """One rung of a server's rank ladder (a row of rank_tiers)."""

    guild_id: int
    tier: int  # 1 = the lowest rank
    role_id: int
    min_xp: int  # server XP needed to earn it


class PersonalVcConfig(NamedTuple):
    """Where personal voice channels live in one server (a row of personal_vc_config)."""

    guild_id: int
    hub_channel_id: int  # the lobby voice channel: join it and you get your own
    panel_channel_id: int  # the text channel with the fixed control panel (#voice-channel-controls)
    panel_message_id: Optional[int]  # the panel message itself, so /personalvc setup can replace it
    staff_role_id: Optional[int]  # moderators: they see and join every personal channel, even hidden ones


class PersonalChannelRow(NamedTuple):
    """One personal voice channel that exists right now, and whose it is (a row of personal_vc_channels)."""

    channel_id: int
    guild_id: int
    owner_id: int


class Database:  # pylint: disable=too-many-public-methods  # all SQL lives here on purpose, one method per query
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
        # Unused since the reaction-roles stub went (Discord onboarding does it now). Kept: a rollback runs
        # older code against this database, and dropping tables isn't forward-compatible.
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
        # The XP rank ladder, per server: tier 1 is the lowest rank (LOWLY SERFS on ours). One row per tier,
        # so a server could grow a longer ladder later without a schema change. See ranks/ladder.py.
        await self.conn.execute('''
            CREATE TABLE IF NOT EXISTS rank_tiers (
                guild_id INTEGER NOT NULL,
                tier INTEGER NOT NULL,
                role_id INTEGER NOT NULL,
                min_xp INTEGER NOT NULL CHECK(min_xp >= 1),
                PRIMARY KEY (guild_id, tier)
            )
        ''')
        # Personal voice channels (personal_vc/, cogs/personal_vc.py), four small tables:
        # where the lobby and panel are per server; which channels exist right now and who owns them (UNIQUE:
        # one channel per person per server); and what each owner wants remembered for next time (mode + guests).
        # No CHECK on mode, so a future mode doesn't need a schema change; the code treats unknown modes as open.
        await self.conn.execute('''
            CREATE TABLE IF NOT EXISTS personal_vc_config (
                guild_id INTEGER PRIMARY KEY,
                hub_channel_id INTEGER NOT NULL,
                panel_channel_id INTEGER NOT NULL,
                panel_message_id INTEGER,
                staff_role_id INTEGER
            )
        ''')
        await self.conn.execute('''
            CREATE TABLE IF NOT EXISTS personal_vc_channels (
                channel_id INTEGER PRIMARY KEY,
                guild_id INTEGER NOT NULL,
                owner_id INTEGER NOT NULL,
                UNIQUE (guild_id, owner_id)
            )
        ''')
        await self.conn.execute('''
            CREATE TABLE IF NOT EXISTS personal_vc_prefs (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                mode TEXT NOT NULL DEFAULT 'open',
                PRIMARY KEY (guild_id, user_id)
            )
        ''')
        await self.conn.execute('''
            CREATE TABLE IF NOT EXISTS personal_vc_guests (
                guild_id INTEGER NOT NULL,
                owner_id INTEGER NOT NULL,
                guest_id INTEGER NOT NULL,
                PRIMARY KEY (guild_id, owner_id, guest_id)
            )
        ''')
        # Added 2026-11 for the rank ladder: XP given rather than earned (see TOTAL_XP_SQL). A new column with a
        # default is forward-compatible: older code simply never looks at it.
        await self._add_column_if_missing("xp", "bonus_xp", "INTEGER NOT NULL DEFAULT 0")
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

    async def _add_column_if_missing(self, table: str, column: str, definition: str) -> None:
        """SQLite has no "ADD COLUMN IF NOT EXISTS", so look first. Only for setup(), with fixed names."""
        async with self.conn.execute(f"PRAGMA table_info({table})") as cursor:
            columns = [row[1] for row in await cursor.fetchall()]
        if column not in columns:
            await self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
            logging.info("Database: added column %s.%s", table, column)

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

    async def get_xp_totals(self, user_id: int) -> XpTotals:
        """Someone's XP, with what it's made of (for /rank)."""
        rows = await self._fetch_all(
            f"SELECT server_xp, bot_xp, bonus_xp, {TOTAL_XP_SQL} FROM xp WHERE user_id = ?", (user_id,)
        )
        return XpTotals(*rows[0]) if rows else XpTotals(0, 0, 0, 0)

    async def get_all_total_xp(self) -> dict[int, int]:
        """Everyone's total XP by user id (for /ladder tidy, which looks at the whole server at once)."""
        rows = await self._fetch_all(f"SELECT user_id, {TOTAL_XP_SQL} FROM xp")
        return dict(rows)

    async def add_server_xp(self, user_id: int, amount: int = 1) -> int:
        """Counts a message and returns the user's new total XP (the rank ladder needs it right away).
        RETURNING hands back the row as it is after the insert/update, so this stays one query."""
        rows = await self._fetch_all(
            f"""
            INSERT INTO xp (user_id, server_xp, bot_xp)
            VALUES (?, ?, 0)
            ON CONFLICT(user_id) DO UPDATE SET server_xp = server_xp + excluded.server_xp
            RETURNING {TOTAL_XP_SQL}
        """,
            (user_id, amount),
            commit=True,
        )
        return rows[0][0]

    async def add_bot_xp(self, user_id: int, amount: int = 1) -> int:
        """Counts a slash command and returns the user's new total XP."""
        rows = await self._fetch_all(
            f"""
            INSERT INTO xp (user_id, server_xp, bot_xp) 
            VALUES (?, 0, ?)
            ON CONFLICT(user_id) DO UPDATE SET bot_xp = bot_xp + excluded.bot_xp
            RETURNING {TOTAL_XP_SQL}
        """,
            (user_id, amount),
            commit=True,
        )
        return rows[0][0]

    async def top_up_xp(self, user_id: int, minimum: int) -> int:
        """Raises someone's total XP to at least `minimum` by adding bonus XP. Never lowers it.
        Returns their new total."""
        rows = await self._fetch_all(
            f"""
            INSERT INTO xp (user_id, server_xp, bot_xp, bonus_xp)
            VALUES (?, 0, 0, ?)
            ON CONFLICT(user_id) DO UPDATE SET bonus_xp = bonus_xp + max(0, excluded.bonus_xp - ({TOTAL_XP_SQL}))
            RETURNING {TOTAL_XP_SQL}
        """,
            (user_id, minimum),
            commit=True,
        )
        return rows[0][0]

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
    async def _fetch_all(self, query: str, parameters: tuple = (), commit: bool = False) -> list:
        """Helper for read queries: runs one SELECT and returns all its rows.
        commit=True is for writes that also return rows (INSERT/UPDATE ... RETURNING)."""
        if self.conn is None:
            raise RuntimeError("Database connection is not initialized. Did you call setup()?")
        async with self.lock:
            try:
                async with self.conn.execute(query, parameters) as cursor:
                    rows = list(await cursor.fetchall())
                if commit:
                    await self.conn.commit()
                return rows
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

    # Rank ladder methods (ranks/ladder.py has the rules; this is just storage)
    async def get_all_rank_tiers(self) -> list[RankTierRow]:
        """Every server's ladder, lowest tier first. Small enough to load once and keep in memory."""
        rows = await self._fetch_all("SELECT guild_id, tier, role_id, min_xp FROM rank_tiers ORDER BY guild_id, tier")
        return [RankTierRow(*row) for row in rows]

    async def set_rank_tiers(self, guild_id: int, tiers: list[tuple[int, int, int]]) -> None:
        """Replaces a server's whole ladder with (tier, role_id, min_xp) rows, all at once: in one transaction,
        so the ladder is never half-saved if something goes wrong in the middle."""
        if self.conn is None:
            raise RuntimeError("Database connection is not initialized. Did you call setup()?")
        async with self.lock:
            try:
                await self.conn.execute("BEGIN IMMEDIATE TRANSACTION")
                await self.conn.execute("DELETE FROM rank_tiers WHERE guild_id = ?", (guild_id,))
                await self.conn.executemany(
                    "INSERT INTO rank_tiers (guild_id, tier, role_id, min_xp) VALUES (?, ?, ?, ?)",
                    [(guild_id, tier, role_id, min_xp) for tier, role_id, min_xp in tiers],
                )
                await self.conn.commit()
            except Exception as e:
                await self.conn.rollback()
                logging.error("Database error saving the rank ladder for guild %s: %s", guild_id, e)
                raise

    async def clear_rank_tiers(self, guild_id: int) -> None:
        """Switches the ladder off for a server (roles members already have are left alone)."""
        await self._execute("DELETE FROM rank_tiers WHERE guild_id = ?", (guild_id,))

    # Personal voice channel methods (personal_vc/rules.py has the rules; this is just storage)
    async def _execute_many(self, query: str, rows: list[tuple]) -> None:
        """Like _execute, but runs one query for each row, all saved together in one commit."""
        if self.conn is None:
            raise RuntimeError("Database connection is not initialized. Did you call setup()?")
        async with self.lock:
            try:
                await self.conn.executemany(query, rows)
                await self.conn.commit()
            except Exception as e:
                await self.conn.rollback()
                logging.error("Database execution error: %s | Query: %s | Rows: %s", e, query, rows)
                raise

    async def get_personal_vc_configs(self) -> list[PersonalVcConfig]:
        """Every server that has personal voice channels switched on. Small enough to keep in memory."""
        rows = await self._fetch_all(
            "SELECT guild_id, hub_channel_id, panel_channel_id, panel_message_id, staff_role_id FROM personal_vc_config"
        )
        return [PersonalVcConfig(*row) for row in rows]

    async def set_personal_vc_config(self, config: PersonalVcConfig) -> None:
        """Saves (or replaces) one server's lobby, panel and staff role."""
        await self._execute(
            """
            INSERT INTO personal_vc_config (guild_id, hub_channel_id, panel_channel_id, panel_message_id, staff_role_id)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET
                hub_channel_id = excluded.hub_channel_id,
                panel_channel_id = excluded.panel_channel_id,
                panel_message_id = excluded.panel_message_id,
                staff_role_id = excluded.staff_role_id
        """,
            tuple(config),
        )

    async def clear_personal_vc_config(self, guild_id: int) -> None:
        """Switches personal channels off for a server. Everyone's saved mode and guests are kept for next time."""
        await self._execute("DELETE FROM personal_vc_config WHERE guild_id = ?", (guild_id,))

    async def add_personal_channel(self, channel_id: int, guild_id: int, owner_id: int) -> None:
        """Remembers a new personal channel. OR REPLACE: if an old row for the same owner is still lying around
        (its channel is long gone), the new one takes its place instead of failing on the UNIQUE rule."""
        await self._execute(
            "INSERT OR REPLACE INTO personal_vc_channels (channel_id, guild_id, owner_id) VALUES (?, ?, ?)",
            (channel_id, guild_id, owner_id),
        )

    async def get_personal_channel_owner(self, channel_id: int) -> Optional[int]:
        """Whose personal channel this is, or None if it isn't one."""
        rows = await self._fetch_all("SELECT owner_id FROM personal_vc_channels WHERE channel_id = ?", (channel_id,))
        return rows[0][0] if rows else None

    async def get_owned_personal_channel(self, guild_id: int, owner_id: int) -> Optional[int]:
        """The channel id of someone's personal channel in this server, or None if they don't have one."""
        rows = await self._fetch_all(
            "SELECT channel_id FROM personal_vc_channels WHERE guild_id = ? AND owner_id = ?", (guild_id, owner_id)
        )
        return rows[0][0] if rows else None

    async def get_all_personal_channels(self) -> list[PersonalChannelRow]:
        """Every personal channel the bot thinks exists, in every server (for the tidy-up at startup)."""
        rows = await self._fetch_all("SELECT channel_id, guild_id, owner_id FROM personal_vc_channels")
        return [PersonalChannelRow(*row) for row in rows]

    async def remove_personal_channel(self, channel_id: int) -> None:
        await self._execute("DELETE FROM personal_vc_channels WHERE channel_id = ?", (channel_id,))

    async def get_personal_vc_mode(self, guild_id: int, user_id: int) -> Optional[str]:
        """Someone's saved mode ('open', 'locked' or 'hidden'), or None if they never picked one."""
        rows = await self._fetch_all(
            "SELECT mode FROM personal_vc_prefs WHERE guild_id = ? AND user_id = ?", (guild_id, user_id)
        )
        return rows[0][0] if rows else None

    async def set_personal_vc_mode(self, guild_id: int, user_id: int, mode: str) -> None:
        if mode not in ('open', 'locked', 'hidden'):
            raise ValueError("mode must be 'open', 'locked' or 'hidden'")
        await self._execute(
            """
            INSERT INTO personal_vc_prefs (guild_id, user_id, mode) VALUES (?, ?, ?)
            ON CONFLICT(guild_id, user_id) DO UPDATE SET mode = excluded.mode
        """,
            (guild_id, user_id, mode),
        )

    async def get_personal_vc_guests(self, guild_id: int, owner_id: int) -> list[int]:
        """Someone's guest list, in the order they were let in. (rowid is SQLite's hidden insertion counter.)"""
        rows = await self._fetch_all(
            "SELECT guest_id FROM personal_vc_guests WHERE guild_id = ? AND owner_id = ? ORDER BY rowid",
            (guild_id, owner_id),
        )
        return [guest_id for (guest_id,) in rows]

    async def add_personal_vc_guests(self, guild_id: int, owner_id: int, guest_ids: list[int]) -> None:
        """Puts people on someone's guest list. Anyone already on it is skipped (OR IGNORE), not doubled."""
        await self._execute_many(
            "INSERT OR IGNORE INTO personal_vc_guests (guild_id, owner_id, guest_id) VALUES (?, ?, ?)",
            [(guild_id, owner_id, guest_id) for guest_id in guest_ids],
        )

    async def remove_personal_vc_guests(self, guild_id: int, owner_id: int, guest_ids: list[int]) -> None:
        await self._execute_many(
            "DELETE FROM personal_vc_guests WHERE guild_id = ? AND owner_id = ? AND guest_id = ?",
            [(guild_id, owner_id, guest_id) for guest_id in guest_ids],
        )
