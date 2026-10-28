import os
import sys
import asyncio
import logging
from pathlib import Path

from dotenv import load_dotenv

from bot import VideoJoker


if __name__ == "__main__":
    # creating necessary directories if they don't exist
    data_dir = Path(__file__).resolve().parent / "data"
    logs_dir = data_dir / "logs"

    logs_dir.mkdir(parents=True, exist_ok=True)

    from logging.handlers import RotatingFileHandler

    # set up logging
    logging.basicConfig(
        level=logging.INFO,  # Set logging level
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            RotatingFileHandler(logs_dir / 'bot.log',
                                maxBytes=5 * 1024 * 1024,  # 5 MB
                                backupCount=3,
                                encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    logging.getLogger("discord").setLevel(logging.INFO)
    logging.getLogger("discord.http").setLevel(logging.WARNING)
    logging.getLogger("discord.gateway").setLevel(logging.WARNING)

    # load env and start the bot
    load_dotenv()
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        logging.error("DISCORD_TOKEN not found in environment variables.")
        sys.exit(1)

    owner = os.getenv('OWNER', '').strip()
    if owner and not owner.isdigit():
        logging.error("OWNER must be your numeric Discord user ID (got %r). See SETUP_GUIDE.md step 2.", owner)
        sys.exit(1)
    if not owner:
        logging.warning("OWNER is not set, so nobody is VIP and nobody can grant VIP. See SETUP_GUIDE.md step 2.")
        os.environ.pop('OWNER', None)  # treat an empty "OWNER=" line in .env the same as no line at all

    bot = VideoJoker(token=token)

    async def run_bot():
        # `async with` guarantees bot.close() runs on the way out (closing the database cleanly),
        # whether the bot stops normally, crashes, or is told to stop.
        async with bot:
            await bot.start_bot()

    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        # Ctrl+C locally, or `docker compose stop` (compose sends SIGINT, see stop_signal)
        logging.info("Shutdown requested, bot stopped.")
