import logging
import discord
from discord import app_commands
from discord.ext.commands import Cog

class ReactionRoles(Cog, name="ReactionRoles"):
    """A cog that handles reaction roles"""
    def __init__(self, bot):
        logging.info("Reaction Roles cog initialized.")
        self.bot = bot

    @app_commands.command(name='create_rr_message', description='Creates a new message that users can react to for a role.')
    # pylint: disable=too-many-arguments, too-many-positional-arguments
    async def create_rr_message(self, interaction: discord.Interaction, title: str, description: str, role: discord.Role, emoji: str) -> None:
        # TODO: Send a formatted embed, add the reaction, and save to DB
        await interaction.response.send_message(
            f"Stub: Created RR message '{title}' ({description}) for role {role.name} with emoji {emoji}",
            ephemeral=True
        )

    @app_commands.command(name='link_rr', description='Links a reaction role to an existing message.')
    async def link_rr(self, interaction: discord.Interaction, message_id: str, role: discord.Role, emoji: str) -> None:
        # TODO: Validate message ID, add reaction to it, and save to DB
        await interaction.response.send_message(f"Stub: Linked RR to message {message_id} for role {role.name} with emoji {emoji}", ephemeral=True)

    @Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id:
            return
            
        # TODO: Look up message_id and emoji in DB
        # role_id = await self.bot.db.get_reaction_role(payload.message_id, str(payload.emoji))
        # if role_id:
        #     role = guild.get_role(role_id)
        #     await member.add_roles(role)

    @Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id:
            return
            
        # TODO: Look up message_id and emoji in DB
        # role_id = await self.bot.db.get_reaction_role(payload.message_id, str(payload.emoji))
        # if role_id:
        #     role = guild.get_role(role_id)
        #     await member.remove_roles(role)

async def setup(bot):
    await bot.add_cog(ReactionRoles(bot))
