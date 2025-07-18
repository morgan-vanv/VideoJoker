import discord
import sys
import os
import asyncio
import logging
from pathlib import Path
from discord import app_commands
from dotenv import load_dotenv


class VideoJoker(discord.Client):
    def __init__(self, intents: discord.Intents):
        intents.message_content = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

        # Loading environment variables
        load_dotenv()
        self.token = os.getenv('DISCORD_TOKEN')

    async def setup_hook(self):
        await self.tree.sync()

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print('------')

    def restart_bot(self):
        os.execv(sys.executable, ['python'] + sys.argv)

    async def on_ready(self):
        logging.info(f"{self.user} is now running.")
        await bot.tree.sync()
        logging.info("commands synced")

    async def on_connect(self):
        logging.info(f"{self.user} has connected.")

    async def start_bot(self):
        await self.start(self.token)

bot = VideoJoker()

@bot.command()
async def ping(ctx):
    await ctx.send('pong')


if __name__ == "__main__":
    asyncio.run(bot.start_bot())