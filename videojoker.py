import discord
import sys
import os
import asyncio
import logging
from pathlib import Path
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

# Importing Cogs
from cogs.games import Games


class VideoJoker(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        intents.message_content = True
        super().__init__(intents=intents, command_prefix="/")

        # Loading environment variables
        load_dotenv()
        self.token = os.getenv('DISCORD_TOKEN')

    async def setup_hook(self):
        # Loads cogs
        await bot.add_cog(Games(bot))

        # Sync commands on startup, after cogs are loaded
        await self.tree.sync()
        logging.info("Commands synced")

    def restart_bot(self):
        os.execv(sys.executable, ['python'] + sys.argv)

    async def on_ready(self):
        logging.info(f"{self.user} is now running and ready to serve!")

    async def on_connect(self):
        logging.info(f"{self.user} has connected.")

    async def start_bot(self):
        await self.start(self.token)


bot = VideoJoker()


# Beginning of the Root level commands exposed to users, the rest are imported from cogs above
@bot.tree.command()
async def ping(ctx):
    logging.info('/ping command invoked')
    await ctx.response.send_message('pong')


@bot.tree.command(name='sync', description='Admin only - Syncs the command tree.')
async def sync(interaction: discord.Interaction):
    # note: adding new commands requires a client restart to show the new commands
    logging.info(f"{interaction.user.name} has activated /sync")
    await bot.tree.sync()
    await interaction.response.send_message('Command tree synced.', delete_after=5)
    logging.info('Command tree synced.')


@bot.tree.command(name='help', description='Shows list of all commands')
async def help(ctx):
    logging.info('/help command invoked')
    embed = discord.Embed(
        title="List of all commands",
        # color=discord.Colour.dark_gray, todo: figure this out later, not working atm
    )
    embed.add_field(name="/ping", value="Returns pong", inline=True)
    embed.add_field(name="/ping", value="Returns pong", inline=False)
    embed.add_field(name="/ping", value="Returns pong", inline=False)
    embed.add_field(name="/ping", value="Returns pong", inline=False)
    await ctx.response.send_message(embed=embed, ephemeral=False)


# Main entry point
if __name__ == "__main__":
    # set up logging
    logging.basicConfig(
        level=logging.INFO,  # Set logging level
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(f"{Path(__file__).resolve().parent / 'bot_log.log'}", mode='w'),
            logging.StreamHandler()
        ]
    )
    logging.getLogger("discord").setLevel(logging.WARNING)

    # running the bot
    load_dotenv()
    asyncio.run(bot.start_bot())
