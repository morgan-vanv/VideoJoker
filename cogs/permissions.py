import logging
import discord
from discord import app_commands
from discord.ext.commands import Cog

from core.custom_exceptions import ExecutingUserNotVIPError

def is_vip():
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.id in interaction.client.db.vips:
            return True
        raise ExecutingUserNotVIPError(interaction.user)
    return app_commands.check(predicate)


class Permissions(Cog, name="Permissions"):
    """**A cog that provides permission-related commands**"""

    def __init__(self, bot):
        logging.info("Permissions cog initialized.")
        self.bot = bot

    @app_commands.command(name='checkpermissions', description='Checks the permissions of a user')
    async def check_permissions(self, interaction: discord.Interaction, user: discord.User) -> None:
        """
        **Replies to the executing user with the permissions of the user provided**

        :param interaction: The interaction object from discord
        :type interaction: discord.Interaction
        :param user: The user whose permissions are to be checked
        :type user: discord.User

        Usage Example: `/checkpermissions @SomeUser`
        """
        logging.info("Permissions check requested for %s by %s", user.name, interaction.user.name)
        await interaction.response.defer()

        if user.id in self.bot.db.banned:
            status = "BANNED"
            color = discord.Colour.red()
        elif user.id in self.bot.db.vips:
            status = "VIP"
            color = discord.Colour.green()
        else:
            status = "No special permissions"
            color = discord.Colour.orange()

        embed = discord.Embed(
            title=f"Permissions for: {user.name}",
            description=f"Status: {status}",
            color=color
        )
        await interaction.followup.send(embed=embed)


    @app_commands.command(name='listbannedusers', description='Lists all banned users')
    async def list_banned_users(self, interaction: discord.Interaction) -> None:
        """
        **Replies to the executing user with a list of all BANNED users**

        Permissions Required: !BANNED

        :param interaction: The interaction object from discord
        :type interaction: discord.Interaction

        Usage Example: `/listbannedusers`
        """
        logging.info("BANNED users list requested by %s", interaction.user.name)
        await interaction.response.defer()

        banned_ids = self.bot.db.banned
        banned_names = []

        for user_id in banned_ids:
            user = await self.bot.fetch_user(user_id)
            banned_names.append(user.mention if user else f"Unknown User ({user_id})")

        description = "\n".join(banned_names) if banned_names else "No banned users found."
        embed = discord.Embed(
            title="BANNED Users",
            description=description,
            color=discord.Colour.red()
        )
        await interaction.followup.send(embed=embed)


    @app_commands.command(name='listvipusers', description='Lists all VIP users')
    async def list_vip_users(self, interaction: discord.Interaction) -> None:
        """
        **Replies to the executing user with a list of all VIP users**

        Permissions Required: !BANNED

        :param interaction: The interaction object from discord
        :type interaction: discord.Interaction

        Usage Example: `/listvipusers`
        """
        logging.info("VIP users list requested by %s", interaction.user.name)
        await interaction.response.defer()

        vip_ids = self.bot.db.vips
        vip_names = []

        for user_id in vip_ids:
            user = await self.bot.fetch_user(user_id)
            vip_names.append(user.mention if user else f"Unknown User ({user_id})")

        description = "\n".join(vip_names) if vip_names else "No VIP users found."
        embed = discord.Embed(
            title="VIP Users",
            description=description,
            color=discord.Colour.green()
        )
        await interaction.followup.send(embed=embed)


    @app_commands.command(name='grantbanuser', description='Bans a user from using the bot')
    @is_vip()
    async def grant_ban_user(self, interaction: discord.Interaction, user: discord.User) -> None:
        """
        **Grants BANNED status to the user provided**

        Permissions Required: VIP

        :param interaction: The interaction object from discord
        :type interaction: discord.Interaction
        :param user: The user to be granted BANNED status
        :type user: discord.User

        Usage Example: `/grantbanuser @SomeUser`
        """
        logging.info("BANNED Status requested for %s by %s", user.name, interaction.user.name)
        await interaction.response.defer()
        
        if user.id == self.bot.db.owner_id:
            await interaction.followup.send("Cannot ban the bot owner.")
            return

        if user.id in self.bot.db.banned:
            await interaction.followup.send(f"User {user.name} is already banned from the bot.")
            return

        await self.bot.db.set_user_role(user.id, 'BANNED')
        logging.info("Added banned user ID to list: %d", user.id)
        await interaction.followup.send(f"User {user.name} has been banned from the bot.")


    @app_commands.command(name='grantvipuser', description='Grants VIP status to a user')
    @is_vip()
    async def grant_vip_user(self, interaction: discord.Interaction, user: discord.User) -> None:
        """
        **Grants VIP status to the user provided**

        Permissions Required: VIP

        :param interaction: The interaction object from discord
        :type interaction: discord.Interaction
        :param user: The user to be granted VIP status
        :type user: discord.User

        Usage Example: `/grantvipuser @SomeUser`
        """
        logging.info("VIP Status requested for %s by %s", user.name, interaction.user.name)
        await interaction.response.defer()

        if user.id in self.bot.db.banned:
            await interaction.followup.send(f"Cannot give user {user.name} VIP status, as they are BANNED.")
            return

        if user.id in self.bot.db.vips:
            await interaction.followup.send(f"User {user.name} already has VIP status.")
            return

        await self.bot.db.set_user_role(user.id, 'VIP')
        logging.info("Added VIP user ID to list: %d", user.id)
        await interaction.followup.send(f"User {user.name} has been granted VIP status.")


    @app_commands.command(name='resetpermissions', description='Resets permissions for a user')
    @is_vip()
    async def reset_permissions(self, interaction: discord.Interaction, user: discord.User) -> None:
        """
        **Resets the permissions of the user provided**

        Permissions Required: !BANNED & VIP

        :param interaction: The interaction object from discord
        :type interaction: discord.Interaction
        :param user: The user to have their permissions reset
        :type user: discord.User

        Usage Example: `/resetpermissions @SomeUser`
        """
        logging.info("Permissions reset requested for %s by %s", user.name, interaction.user.name)
        await interaction.response.defer()
        
        await self.bot.db.remove_user_role(user.id)
        await interaction.followup.send(f"Permissions for user {user.name} have been reset.")
        logging.info("Permissions reset for user: %s (ID: %d)", user.name, user.id)

async def setup(bot):
    await bot.add_cog(Permissions(bot))
