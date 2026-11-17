"""Raffles: someone puts up a prize, people react 🎟️ to enter, and the bot draws the winner when time's up.

/raffle start prize duration [winners] posts the raffle card in the channel and adds the first 🎟️ itself, so people
can see where to click. Anyone can start one, one at a time per person in each server.
/raffle cancel [raffle] calls it off (no winner), /raffle end [raffle] draws it early. The host can do both to their
own raffle; VIPs can do them to anyone's (the raffle option suggests the running ones).

How it works:
- Every raffle is a row in the raffles table, so a restart (every deploy is one) doesn't lose it. A check every 30
  seconds draws any raffle whose time is up, including one that ended while the bot was down.
- Entries are the 🎟️ reactions on the card, read once at the draw: no list to keep in sync, and taking your
  reaction off means you're out. Bots, banned users and the host can't win (raffle/rules.py).
- The winner line under the card pings the winners and nobody else (an explicit AllowedMentions).

Needs, in the raffle's channel: View Channel, Send Messages, Embed Links, Add Reactions, Read Message History (all
already in the bot's server-wide set). No intents beyond the defaults: reactions are read from the message itself.

The rules are in raffle/rules.py, the card in raffle/card.py and every line it shows in raffle/lines.py.
"""

import logging
from enum import Enum
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks

from core.database import RaffleRow
from raffle import card, lines, rules

# What the bot needs in the channel: discord.py's name for each permission, then how Discord's UI says it
NEEDED = {
    "view_channel": "View Channel",
    "send_messages": "Send Messages",
    "embed_links": "Embed Links",
    "add_reactions": "Add Reactions",
    "read_message_history": "Read Message History",
}


class Outcome(Enum):
    """How a draw went, so /raffle end can tell its user."""

    DRAWN = "drawn"
    NOT_RUNNING = "not running"  # someone else ended or cancelled it first
    GONE = "gone"  # the card (or its channel) is gone, or the bot can't see it any more: the raffle is closed
    TRY_AGAIN = "try again"  # Discord hiccuped before anything was announced: the raffle is still running


def missing(permissions: discord.Permissions, in_thread: bool) -> list[str]:
    """Which of the NEEDED permissions are missing, as Discord's UI names them. In a thread, posting takes "Send
    Messages in Threads" instead of "Send Messages"."""
    needed = dict(NEEDED)
    if in_thread:
        del needed["send_messages"]
        needed["send_messages_in_threads"] = "Send Messages in Threads"
    return [label for name, label in needed.items() if not getattr(permissions, name)]


def link(raffle: RaffleRow) -> str:
    """A link straight to the raffle card."""
    return f"https://discord.com/channels/{raffle.guild_id}/{raffle.channel_id}/{raffle.message_id}"


@app_commands.guild_only()
class Raffle(commands.GroupCog, group_name="raffle", group_description=lines.GROUP):
    """Raffles: put up a prize, people react to enter, a winner is drawn"""

    def __init__(self, bot):
        logging.info("Raffle cog initialized.")
        self.bot = bot

    async def cog_load(self):
        self.tick.start()

    async def cog_unload(self):
        self.tick.cancel()

    # ---- the commands

    @app_commands.command(name="start", description=lines.START)
    @app_commands.describe(prize=lines.START_PRIZE, duration=lines.START_DURATION, winners=lines.START_WINNERS)
    async def start(
        self,
        interaction: discord.Interaction,
        prize: app_commands.Range[str, 1, 200],
        duration: str,
        winners: app_commands.Range[int, 1, rules.MOST_WINNERS] = 1,
    ) -> None:
        try:
            length = rules.parse_duration(duration)
        except ValueError as error:
            problem = {"too short": lines.TOO_SHORT, "too long": lines.TOO_LONG}.get(str(error), lines.BAD_DURATION)
            text = discord.utils.escape_markdown(duration)
            await interaction.response.send_message(problem.format(text=text), ephemeral=True)
            return

        # app_permissions: what the bot itself may do in the channel the command was used in
        in_thread = isinstance(interaction.channel, discord.Thread)
        if needs := missing(interaction.app_permissions, in_thread):
            await interaction.response.send_message(lines.CANT_HERE.format(missing=", ".join(needs)), ephemeral=True)
            return

        existing = await self.bot.db.get_hosts_raffle(interaction.guild_id, interaction.user.id)
        if existing:
            await interaction.response.send_message(lines.ALREADY_RUNNING.format(link=link(existing)), ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)  # posting the card and its reaction can take a moment
        finish = discord.utils.utcnow() + length
        try:
            message = await interaction.channel.send(embed=card.running(prize, interaction.user.id, winners, finish))
        except discord.HTTPException as error:
            logging.warning("Raffle: couldn't post a raffle card in channel %s: %s", interaction.channel_id, error)
            await interaction.followup.send(lines.START_FAILED, ephemeral=True)
            return
        await self.bot.db.add_raffle(
            interaction.guild_id,
            interaction.channel_id,
            message.id,
            interaction.user.id,
            prize,
            winners,
            int(finish.timestamp()),
        )
        try:
            await message.add_reaction(rules.TICKET)
        except discord.HTTPException as error:
            # Not fatal: people can still add the 🎟️ themselves
            logging.warning("Raffle: couldn't add the first ticket reaction: %s", error)
        await interaction.followup.send(lines.STARTED.format(relative=lines.stamp(finish, "R")), ephemeral=True)

    @app_commands.command(name="cancel", description=lines.CANCEL)
    @app_commands.describe(raffle=lines.WHICH)
    async def cancel(self, interaction: discord.Interaction, raffle: Optional[str] = None) -> None:
        chosen = await self.pick(interaction, raffle)
        if chosen is None:
            return
        if not await self.bot.db.close_raffle(chosen.id, "cancelled"):
            await interaction.response.send_message(lines.NOT_RUNNING, ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            message = await self.card_message(chosen)
            await message.edit(embed=card.cancelled(chosen.prize, chosen.host_id, interaction.user.id))
        except discord.HTTPException as error:
            # It's cancelled either way; the card just still looks open (or is gone already)
            logging.info("Raffle: cancelled raffle %s, but couldn't update its card: %s", chosen.id, error)
        await interaction.followup.send(lines.CANCELLED.format(prize=lines.prize(chosen.prize)), ephemeral=True)

    @app_commands.command(name="end", description=lines.END)
    @app_commands.describe(raffle=lines.WHICH)
    async def end(self, interaction: discord.Interaction, raffle: Optional[str] = None) -> None:
        chosen = await self.pick(interaction, raffle)
        if chosen is None:
            return
        await interaction.response.defer(ephemeral=True)  # reading everyone's reactions can take a moment
        outcome = await self.draw(chosen)
        reply = {
            Outcome.DRAWN: lines.DRAWN.format(link=link(chosen)),
            Outcome.NOT_RUNNING: lines.NOT_RUNNING,
            Outcome.GONE: lines.GONE,
            Outcome.TRY_AGAIN: lines.TRY_AGAIN,
        }[outcome]
        await interaction.followup.send(reply, ephemeral=True)

    async def pick(self, interaction: discord.Interaction, choice: Optional[str]) -> Optional[RaffleRow]:
        """The raffle that /raffle cancel or /raffle end is about: the one picked in the raffle option (its id,
        filled in by the suggestions, or a prize typed by hand), or else the user's own. Replies and returns None
        when there isn't one, or it isn't theirs and they're not a VIP."""
        if choice:
            raffle = await self.find(interaction.guild_id, choice)
            if raffle is None:
                await interaction.response.send_message(lines.NOT_RUNNING, ephemeral=True)
                return None
        else:
            raffle = await self.bot.db.get_hosts_raffle(interaction.guild_id, interaction.user.id)
            if raffle is None:
                await interaction.response.send_message(lines.NONE_RUNNING, ephemeral=True)
                return None
        if raffle.host_id != interaction.user.id and interaction.user.id not in self.bot.db.vips:
            await interaction.response.send_message(lines.NOT_YOURS, ephemeral=True)
            return None
        return raffle

    async def find(self, guild_id: int, choice: str) -> Optional[RaffleRow]:
        """A running raffle in this server, by id (what a suggestion fills in) or by its prize (typed by hand)."""
        running = await self.bot.db.get_running_raffles(guild_id)
        typed = choice.strip().casefold()
        for raffle in running:
            if typed in (str(raffle.id), raffle.prize.strip().casefold()):
                return raffle
        return None

    # Autocomplete: as you fill in the raffle option, Discord asks the bot for suggestions. Everyone sees their own
    # running raffle; VIPs see every running raffle in the server. Stacking the decorators hooks it up to both.
    @cancel.autocomplete("raffle")
    @end.autocomplete("raffle")
    async def which_raffle(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        running = await self.bot.db.get_running_raffles(interaction.guild_id)
        if interaction.user.id not in self.bot.db.vips:
            running = [raffle for raffle in running if raffle.host_id == interaction.user.id]
        typed = current.casefold()
        choices = []
        for raffle in running:
            if typed not in raffle.prize.casefold():
                continue
            host = interaction.guild.get_member(raffle.host_id)
            name = lines.CHOICE.format(prize=raffle.prize, host=host.display_name if host else raffle.host_id)
            choices.append(app_commands.Choice(name=name[:100], value=str(raffle.id)))  # Discord: 100 characters max
        return choices[:25]  # Discord shows at most 25 suggestions

    # ---- the draw

    async def card_message(self, raffle: RaffleRow) -> discord.Message:
        """Fetches the raffle card from Discord. A partial messageable works for any kind of channel (text, thread,
        a voice channel's chat) without needing it in the bot's cache."""
        channel = self.bot.get_partial_messageable(raffle.channel_id, guild_id=raffle.guild_id)
        return await channel.fetch_message(raffle.message_id)

    @staticmethod
    async def entrants(message: discord.Message) -> list[int]:
        """Everyone (but bots) who reacted with the ticket, right now."""
        reaction = next((reaction for reaction in message.reactions if rules.is_ticket(reaction.emoji)), None)
        if reaction is None:
            return []
        return [user.id async for user in reaction.users() if not user.bot]

    async def draw(self, raffle: RaffleRow) -> Outcome:
        """Draws a raffle's winners, updates its card and posts the winner line under it.

        It's marked drawn first, so a cancel (or a second /raffle end) arriving at the same moment can't also go
        ahead. If Discord hiccups before anything is announced, it's put back to running and tried again; once the
        card shows the winners, the draw is final (so a retry can never pick different winners).
        """
        if not await self.bot.db.close_raffle(raffle.id, "drawn"):
            return Outcome.NOT_RUNNING
        try:
            message = await self.card_message(raffle)
            entries = rules.eligible(await self.entrants(message), raffle.host_id, self.bot.db.banned)
            winners = rules.pick_winners(entries, raffle.winners)
            result = card.over(raffle.prize, raffle.host_id, winners, len(entries), discord.utils.utcnow())
            await message.edit(embed=result)
        except (discord.NotFound, discord.Forbidden) as error:
            # The card or its channel is gone, or the bot can't see it any more: nothing to draw from
            logging.warning("Raffle: closed raffle %s, its card can't be reached: %s", raffle.id, error)
            await self.bot.db.set_raffle_state(raffle.id, "cancelled")
            return Outcome.GONE
        except discord.HTTPException as error:
            logging.warning("Raffle: drawing raffle %s failed, trying again soon: %s", raffle.id, error)
            await self.bot.db.set_raffle_state(raffle.id, "running")
            return Outcome.TRY_AGAIN

        # Ping the winners and nobody else (not the host, not anyone named in the prize)
        mentions = discord.AllowedMentions(
            everyone=False, roles=False, users=[discord.Object(id=user_id) for user_id in winners]
        )
        try:
            await message.reply(card.won_message(raffle.prize, winners), allowed_mentions=mentions)
        except discord.HTTPException as error:
            logging.warning("Raffle: raffle %s is drawn, but the winner line couldn't be posted: %s", raffle.id, error)
        logging.info("Raffle: drew raffle %s (%d entries, %d winners).", raffle.id, len(entries), len(winners))
        return Outcome.DRAWN

    # ---- the clock: every 30 seconds, draw the raffles whose time is up

    @tasks.loop(seconds=30)
    async def tick(self):
        try:
            due = await self.bot.db.get_due_raffles(int(discord.utils.utcnow().timestamp()))
        except Exception:  # an unhandled error inside a tasks.loop would stop it for good
            logging.exception("Raffle: couldn't look up the raffles that are due; trying again soon.")
            return
        for raffle in due:
            try:
                await self.draw(raffle)
            except Exception:
                logging.exception("Raffle: drawing raffle %s failed.", raffle.id)

    @tick.before_loop
    async def before_tick(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(Raffle(bot))
