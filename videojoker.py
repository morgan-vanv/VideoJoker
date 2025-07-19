""" This is the main file for the VideoJoker Discord bot. """

# standard imports
import sys
import os
import asyncio
import logging
from pathlib import Path

# third party imports
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

# Importing Cogs
from cogs.games import Games
from cogs.fun import Fun
from cogs.utility import Utility


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
        await bot.add_cog(Fun(bot))
        await bot.add_cog(Utility(bot))

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
        title="Help - List of Commands",
        description="Here are all the available commands:",
        # color=discord.Colour.blue() # TODO: figure out why this isn't working
    )

    # Root-level commands
    embed.add_field(name="/ping", value="Returns pong", inline=False)
    embed.add_field(name="/sync", value="Admin only - Syncs the command tree.", inline=False)
    embed.add_field(name="/help", value="Shows list of all commands", inline=False)

    # Games cog commands
    embed.add_field(name="/coinflip", value="Flips a coin.", inline=False)
    embed.add_field(name="/diceroll", value="Rolls an N-sided die (defaults to 6).", inline=False)

    # Fun cog commands
    embed.add_field(name="/roast", value="Roast a user.", inline=False)
    embed.add_field(name="/say", value="Repeat after me.", inline=False)

    # Utility cog commands
    embed.add_field(name="/userinfo", value="Displays information about a user.", inline=False)
    embed.add_field(name="/serverinfo", value="Displays information about the server.", inline=False)

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
