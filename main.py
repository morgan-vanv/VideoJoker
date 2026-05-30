import os
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

    # set up logging
    logging.basicConfig(
        level=logging.INFO,  # Set logging level
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(logs_dir / 'bot.log',
                                mode='w',
                                encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    logging.getLogger("discord").setLevel(logging.WARNING)

    # load env and start the bot
    load_dotenv()
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        logging.error("DISCORD_TOKEN not found in environment variables.")
        exit(1)

    bot = VideoJoker(token=token)
    asyncio.run(bot.start_bot())
