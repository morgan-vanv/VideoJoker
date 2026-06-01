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
    permissions_dir = data_dir / "permissions"
    logs_dir = data_dir / "logs"

    permissions_dir.mkdir(parents=True, exist_ok=True)
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

    bot = VideoJoker(token=token)
    asyncio.run(bot.start_bot())
