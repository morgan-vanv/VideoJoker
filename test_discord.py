import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
token = os.getenv("DISCORD_TOKEN")

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.default())

    async def setup_hook(self):
        await self.tree.sync()

bot = MyBot()

@bot.tree.command(name="testcmd")
async def testcmd(interaction: discord.Interaction):
    await interaction.response.send_message("Starting...", ephemeral=False)
    
    class MyView(discord.ui.View):
        def __init__(self, inv):
            super().__init__()
            self.inv = inv
        @discord.ui.button(label="Click me", style=discord.ButtonStyle.primary)
        async def click(self, inter: discord.Interaction, button: discord.ui.Button):
            await inter.response.edit_message(content="Clicked!", view=None)
            await self.inv.edit_original_response(content="Final Result!")

    await interaction.followup.send("Ephemeral msg", view=MyView(interaction), ephemeral=True)

bot.run(token)
