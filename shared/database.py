import aiosqlite
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "videojoker.db"

async def setup_database():
    """Initializes the SQLite database and creates necessary tables."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS permissions (
                user_id INTEGER PRIMARY KEY,
                is_vip BOOLEAN DEFAULT 0,
                is_banned BOOLEAN DEFAULT 0
            )
        ''')
        await db.commit()

def get_db():
    """Returns an aiosqlite connection to the database."""
    return aiosqlite.connect(DB_PATH)
