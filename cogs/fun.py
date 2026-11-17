import logging
import random
import discord
from discord import app_commands
from discord.ext.commands import Cog

from core.constants import CURSE_OF_RA_FIRST_GLYPH, CURSE_OF_RA_LAST_GLYPH, CURSE_OF_RA_LENGTH


def curse_of_ra(target: str) -> str:
    """Builds the Curse of Ra for `target` (a mention like <@123>): a random wall of hieroglyphs"""

    # chr() turns a Unicode number into its character, so each pick is one random hieroglyph
    glyphs = "".join(
        chr(random.randint(CURSE_OF_RA_FIRST_GLYPH, CURSE_OF_RA_LAST_GLYPH)) for _ in range(CURSE_OF_RA_LENGTH)
    )
    return f"**shut up, {target}** {glyphs} **(CURSE OF RA)**"


class Fun(Cog, name="Fun"):
    """A cog that provides fun commands"""

    def __init__(self, bot):
        logging.info("Fun cog initialized.")
        self.bot = bot

    @app_commands.command(name='say', description='Repeat after me')
    # Range makes Discord itself cap the message at 2000 characters, the most one Discord message can hold
    async def say(self, interaction: discord.Interaction, message: app_commands.Range[str, 1, 2000]) -> None:
        """Repeats the given message"""

        await interaction.response.send_message(message, allowed_mentions=discord.AllowedMentions.none())

    @app_commands.command(name='curseofra', description='shut up, bozo. Curse a user with the Curse of Ra')
    async def curseofra(self, interaction: discord.Interaction, user: discord.User) -> None:
        """Curses a user with the Curse of Ra (the meme) and pings them so they know"""

        # Ping exactly the cursed user and nobody else
        await interaction.response.send_message(
            curse_of_ra(user.mention), allowed_mentions=discord.AllowedMentions(users=[user])
        )

    @app_commands.command(name='russianroulette', description='Play russian roulette')
    async def russianroulette(self, interaction: discord.Interaction) -> None:
        """Game of Russian Roulette"""

        roll = random.randint(1, 6)

        if roll == 1:
            await interaction.response.send_message(f"Boom! You are dead comrade.")
        else:
            await interaction.response.send_message(f"You live another day comrade.")


async def setup(bot):
    await bot.add_cog(Fun(bot))
