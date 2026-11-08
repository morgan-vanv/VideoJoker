import logging
import time
from typing import Optional

import discord
from discord import app_commands
from discord.ext.commands import Cog

from cogs.ranks import ladder_of, rank_label
from core.database import COMMAND_XP_COOLDOWN_SECONDS
from ranks.ladder import rank_progress
from standing import lines
from standing.board import Placing, place_of, placings, top_with_you
from standing.rewards import command_xp_due
from standing.ui import LeaderboardView


def server_board(guild: discord.Guild, scores: dict[int, int]) -> list[Placing]:
    """XP and USh are kept per person, not per server, so a server's board is everyone's score filtered down to the
    (human) members of this server. guild.members is the full list thanks to the members intent (bot.py)."""
    return placings({member.id: scores.get(member.id, 0) for member in guild.members if not member.bot})


class Utility(Cog, name="Utility"):
    """A cog that provides utility commands"""

    def __init__(self, bot):
        logging.info("Utility cog initialized.")
        self.bot = bot
        # When each person's last command earned XP (time.monotonic() seconds), for the command XP cooldown.
        # Only in memory: a restart forgets it, which at worst means one extra early reward.
        self.last_command_xp: dict[int, float] = {}

    @app_commands.command(name='userinfo', description='Displays information about a user')
    async def userinfo(self, interaction: discord.Interaction, user: discord.User) -> None:
        """
        **Displays information about a user**

        :param interaction: The interaction object from discord
        :type interaction: discord.Interaction
        :param user: The Discord user to get information about.
        :type user: discord.User

        Usage Example: `/userinfo @SomeUser`
        """
        embed = discord.Embed(
            title=f"User Info: {user.name}",
            description=f"Nickname: {user.display_name}\n"
            f"ID: {user.id}\n"
            f"Joined Discord: {user.created_at.strftime('%Y-%m-%d')}",
            color=discord.Colour.blue(),
        )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name='serverinfo', description='Displays information about the server')
    @app_commands.guild_only()
    async def serverinfo(self, interaction: discord.Interaction) -> None:
        """
        **Displays information about the server**

        :param interaction: The interaction object from discord
        :type interaction: discord.Interaction

        Usage Example: `/serverinfo`
        """
        guild = interaction.guild
        embed = discord.Embed(
            title=f"Server Info: {guild.name}",
            description=f"ID: {guild.id}\n"
            f"Member Count: {guild.member_count}\n"
            f"Created: {guild.created_at.strftime('%Y-%m-%d')}",
            color=discord.Colour.green(),
        )
        await interaction.response.send_message(embed=embed)

    @Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is None:
            return
        # Every message counts (1 XP, see core/database.py)
        total = await self.bot.db.add_server_xp(message.author.id, 1)
        # Tell anyone who cares (the rank ladder, cogs/ranks.py) about the new total. dispatch("x") calls
        # every listener named on_x, the same way Discord's own events reach on_message.
        self.bot.dispatch("xp_gained", message.author, total)

    @Cog.listener()
    async def on_app_command_completion(
        self,
        interaction: discord.Interaction,
        _command: discord.app_commands.Command | discord.app_commands.ContextMenu,
    ):
        # A completed command earns XP (5, see core/database.py), but at most once a minute per person
        if interaction.user.bot:
            return
        await self.reward_command(interaction.user)

    async def reward_command(self, user: discord.Member | discord.User) -> Optional[int]:
        """Counts a command for XP if the cooldown allows it. Returns the new XP total, or None if this one was too
        soon after the last reward (then nothing changes, and the ladder isn't told: there's nothing new)."""
        now = time.monotonic()
        if not command_xp_due(self.last_command_xp.get(user.id), now, COMMAND_XP_COOLDOWN_SECONDS):
            return None
        self.last_command_xp[user.id] = now
        total = await self.bot.db.add_bot_xp(user.id, 1)
        self.bot.dispatch("xp_gained", user, total)
        return total

    @app_commands.command(name='rank', description="Check your or another member's XP, rank and place on the server.")
    async def rank(self, interaction: discord.Interaction, user: discord.User | None = None) -> None:
        target_user = user or interaction.user
        if target_user.bot:
            await interaction.response.send_message(lines.RANK_BOT, ephemeral=True)
            return
        guild = interaction.guild  # None in DMs: then there's no ladder and no server place to show
        xp = await self.bot.db.get_xp_totals(target_user.id)
        balance = await self.bot.db.get_balance(target_user.id)

        description = []
        tiers = ladder_of(self.bot, guild)
        if tiers:
            # Their rank is the ladder role they wear, so look them up as a member of this server (a plain User,
            # e.g. someone who left, has no roles here; then rank_progress goes by their XP instead)
            member = guild.get_member(target_user.id)
            progress = rank_progress(tiers, xp.total, {role.id for role in member.roles} if member else set())

            def label(tier):
                return rank_label(guild, tier)

            description += [lines.rank_line(progress, label), lines.progress_line(progress, label)]
        if guild is not None:
            board = server_board(guild, await self.bot.db.get_all_total_xp())
            description.append(lines.xp_line(xp.total, place_of(board, target_user.id), len(board)))
        else:
            description.append(lines.xp_line(xp.total, None, None))
        description.append(lines.ush_line(balance))
        description.append(f"\n{lines.RANK_POINTER}")

        embed = discord.Embed(
            title=lines.RANK_TITLE.format(name=target_user.display_name),
            description="\n".join(description),
            color=discord.Colour.purple(),
        )
        if xp.total:
            # The small print: what the XP is made of
            breakdown = f"{xp.messages:,} messages · {xp.commands:,} commands"
            if xp.bonus:
                breakdown += f" · {xp.bonus:,} carried over from the old ranks"
            embed.add_field(name=lines.BREAKDOWN_HEADING, value=breakdown, inline=False)
        embed.set_footer(text=lines.EARNING)
        # Public, so friends can show off, but looking someone up never pings them
        await interaction.response.send_message(embed=embed, allowed_mentions=discord.AllowedMentions.none())

    def board_embed(self, board: str, rows: list[Placing], viewer: discord.abc.User) -> discord.Embed:
        """One leaderboard ("xp" or "ush"): the top 10, plus the viewer's own row if they're further down."""
        unit = lines.UNITS[board]
        shown, your_row = top_with_you(rows, viewer.id)
        text = [lines.board_row(row, unit, row.user_id == viewer.id) for row in shown]
        if not shown:
            text.append(lines.BOARD_EMPTY)
        if your_row is not None:
            text += ["…", lines.board_row(your_row, unit, is_you=True)]
        elif place_of(rows, viewer.id) is None and shown:
            text += ["", lines.NOT_ON_BOARD[board]]
        if rows:
            text += ["", lines.board_count(len(rows))]
        embed = discord.Embed(title=lines.BOARD_TITLES[board], description="\n".join(text), color=discord.Colour.gold())
        embed.set_footer(text=lines.EARNING)
        return embed

    @app_commands.command(name='leaderboard', description="The server's top 10 for XP and USh, and where you stand.")
    @app_commands.guild_only()
    async def leaderboard(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        # Both boards are worked out now, so a button click never needs the database
        boards = {
            "xp": server_board(guild, await self.bot.db.get_all_total_xp()),
            "ush": server_board(guild, await self.bot.db.get_all_balances()),
        }

        def make_embed(board: str, viewer: discord.abc.User) -> discord.Embed:
            return self.board_embed(board, boards[board], viewer)

        view = LeaderboardView(interaction.user, make_embed)
        # Mentions inside an embed never ping, and allowed_mentions=none() makes sure the message can't either
        await interaction.response.send_message(
            embed=make_embed("xp", interaction.user), view=view, allowed_mentions=discord.AllowedMentions.none()
        )
        view.message = await interaction.original_response()


async def setup(bot):
    await bot.add_cog(Utility(bot))
