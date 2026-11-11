"""Event alerts: the VJ's heads-up for a server's own Discord events.

Discord already does the events themselves: making one (Events at the top of the channel list; any link, like the
Foundry table, can be its location), weekly repeats, cancelling or moving one week, and the RSVP ("Interested").
It also notifies the Interested people when an event starts. What it doesn't do, and what this cog adds:

1. Reminders before the start (by default the day before and an hour before) in the server's alert channel. They
   ping everyone marked Interested and end with the event's link, which Discord shows as the event's card with its
   Interested button, so latecomers can still click it.
2. A notice when someone edits an event in Discord and its time or location changes, or it's cancelled, pinging
   the people who were Interested. There's no command for this: the bot just watches the edits.

The one command, /seteventalerts [channel], switches it on for a server (with a channel) or off (without one).
The reminder times are one setting for the whole bot: EVENT_ALERT_TIMES in .env (e.g. "24h,1h"), optional.

Needs, in the alert channel: View Channel, Send Messages and Embed Links (for the event card). Nothing else: the
bot never makes or edits events, and Discord sends event changes with the default intents.

The rules (which reminder is due, which edits count) are in event_alerts/rules.py and tested there. Every line it
posts is in event_alerts/lines.py (plain on purpose: schedule notices, not flavour).
"""

import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks

from cogs.permissions import is_vip
from event_alerts import lines, rules
from event_alerts.rules import Change, EventState

# What the bot needs in the alert channel: discord.py's name for each permission, then how Discord's UI says it
NEEDED = {"view_channel": "View Channel", "send_messages": "Send Messages", "embed_links": "Embed Links"}

# Records of sent reminders older than this are dropped at startup: those events are long over
FORGET_AFTER = timedelta(days=30)


def reminders_from_env() -> tuple[int, ...]:
    """The reminder times from EVENT_ALERT_TIMES, or the defaults if it's not set. A typo there falls back to the
    defaults with a warning (rather than switching reminders off), so a bad edit can't silence game night."""
    text = os.getenv("EVENT_ALERT_TIMES", "").strip()
    if not text:
        return rules.DEFAULT_REMINDERS
    try:
        return rules.parse_reminders(text)
    except ValueError as error:
        logging.warning(
            "Event alerts: EVENT_ALERT_TIMES %s. Using the defaults (%s) instead.",
            error,
            rules.describe_reminders(rules.DEFAULT_REMINDERS),
        )
        return rules.DEFAULT_REMINDERS


def state_of(event: discord.ScheduledEvent) -> EventState:
    return EventState(event.name, event.start_time, event.location, event.status.name)


def missing(channel: discord.abc.GuildChannel) -> list[str]:
    """Which of the NEEDED permissions the bot doesn't have in this channel, as Discord's UI names them."""
    have = channel.permissions_for(channel.guild.me)
    return [label for name, label in NEEDED.items() if not getattr(have, name)]


@dataclass
class PendingNotice:
    """An event someone is editing right now: how it looked before their first edit, and who was Interested then
    (once an event is deleted, Discord can no longer say who was)."""

    guild_id: int
    before: EventState
    interested: set[int]
    since: datetime  # when the first edit arrived
    timer: Optional[asyncio.Task] = None


class EventAlerts(commands.Cog):
    """Reminders before a server's Discord events, and a notice when one is moved or cancelled"""

    def __init__(self, bot):
        logging.info("Event alerts cog initialized.")
        self.bot = bot
        self.reminders = reminders_from_env()
        # Server id -> alert channel id, for every server with alerts on. Kept in memory: read every minute.
        self.channels: dict[int, int] = {}
        # Event id -> who's marked Interested (user ids). Memory only: filled from Discord at startup, then kept up
        # to date as people click. It's for the cancel notice, when the event is gone and Discord can't be asked.
        self.interested: dict[int, set[int]] = {}
        # Event id -> an edit waiting out NOTICE_DELAY, so a round of quick edits makes one notice
        self.pending: dict[int, PendingNotice] = {}
        # (server id, problem) pairs already in the log, so a missing permission is logged once, not every minute
        self.warned: set[tuple[int, str]] = set()

    async def cog_load(self):
        self.channels = await self.bot.db.get_event_alert_channels()
        long_ago = discord.utils.utcnow() - FORGET_AFTER
        await self.bot.db.forget_event_reminders_before(int(long_ago.timestamp()))
        if self.channels:
            logging.info(
                "Event alerts: on in %d server(s), reminders %s before.",
                len(self.channels),
                rules.describe_reminders(self.reminders),
            )
        else:
            # Hosting contract: a feature with nothing set up switches off and says so, the bot still starts
            logging.warning("Event alerts: off (no server has run /seteventalerts yet).")
        self.tick.start()

    async def cog_unload(self):
        self.tick.cancel()
        for pending in self.pending.values():
            if pending.timer:
                pending.timer.cancel()

    def warn_once(self, guild: discord.Guild, problem: str) -> None:
        if (guild.id, problem) in self.warned:
            return
        self.warned.add((guild.id, problem))
        logging.warning("Event alerts in '%s': %s", guild.name, problem)

    def alert_channel(self, guild: discord.Guild) -> Optional[discord.TextChannel]:
        """The server's alert channel, if alerts are on there and the bot can post in it."""
        channel_id = self.channels.get(guild.id)
        if channel_id is None:
            return None
        channel = guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            self.warn_once(guild, "the alert channel is gone (deleted?). Run /seteventalerts again.")
            return None
        if needs := missing(channel):
            self.warn_once(guild, f"I need {', '.join(needs)} in #{channel.name}.")
            return None
        return channel

    # ---- the command

    @app_commands.command(
        name="seteventalerts", description="Pick where the VJ posts event reminders. Leave it empty to switch them off."
    )
    @app_commands.describe(channel="Where reminders and changes to this server's events go (empty = alerts off)")
    @app_commands.guild_only()
    # Out of the / menu for everyone but admins (the server owner can show it to other roles in Integrations)
    @app_commands.default_permissions(manage_guild=True)
    @is_vip()
    async def set_event_alerts(self, interaction: discord.Interaction, channel: Optional[discord.TextChannel] = None):
        guild = interaction.guild
        if channel is None:
            await self.bot.db.clear_event_alert_channel(guild.id)
            self.channels.pop(guild.id, None)
            logging.info("Event alerts: switched off in '%s'.", guild.name)
            await interaction.response.send_message(lines.OFF, ephemeral=True)
            return

        if needs := missing(channel):
            await interaction.response.send_message(
                lines.CANT_POST.format(channel=channel.mention, missing=", ".join(needs)), ephemeral=True
            )
            return

        await self.bot.db.set_event_alert_channel(guild.id, channel.id)
        self.channels[guild.id] = channel.id
        # A fresh start for this server's warnings: if the new channel breaks too, the log should say so again
        self.warned = {(guild_id, problem) for guild_id, problem in self.warned if guild_id != guild.id}
        logging.info("Event alerts: on in '%s', posting in #%s.", guild.name, channel.name)
        await interaction.response.send_message(
            lines.SET.format(times=rules.describe_reminders(self.reminders), channel=channel.mention), ephemeral=True
        )

    # ---- who's Interested

    async def fetch_interested(self, event: discord.ScheduledEvent) -> set[int]:
        """Asks Discord who's marked Interested right now (and remembers it). If Discord doesn't answer, what we
        remember will do."""
        try:
            ids = {user.id async for user in event.users() if not user.bot}
        except discord.HTTPException as error:
            logging.warning("Event alerts: couldn't ask Discord who's interested in '%s': %s", event.name, error)
            return set(self.interested.get(event.id, set()))
        self.interested[event.id] = ids
        return set(ids)

    @commands.Cog.listener()
    async def on_scheduled_event_user_add(self, event: discord.ScheduledEvent, user: discord.User):
        if not user.bot and event.id in self.interested:
            self.interested[event.id].add(user.id)

    @commands.Cog.listener()
    async def on_scheduled_event_user_remove(self, event: discord.ScheduledEvent, user: discord.User):
        self.interested.get(event.id, set()).discard(user.id)

    # ---- reminders: a look at every event once a minute

    @tasks.loop(minutes=1)
    async def tick(self):
        now = discord.utils.utcnow()
        for guild_id in list(self.channels):
            guild = self.bot.get_guild(guild_id)
            if guild is None or guild.unavailable:
                continue  # not in that server any more, or Discord is having a moment
            try:
                await self.check_guild(guild, now)
            except Exception:  # an unhandled error inside a tasks.loop would stop it for good
                logging.exception("Event alerts: checking '%s' failed; trying again next minute.", guild.name)

    @tick.before_loop
    async def before_tick(self):
        await self.bot.wait_until_ready()

    async def check_guild(self, guild: discord.Guild, now: datetime) -> None:
        channel = self.alert_channel(guild)
        if channel is None:
            return
        for event in guild.scheduled_events:
            if event.status is not discord.EventStatus.scheduled or event.id in self.pending:
                continue  # running, over, or being edited right now (its notice decides what happens next)
            if event.id not in self.interested:
                await self.fetch_interested(event)  # first look at this event since startup
            starts_at = int(event.start_time.timestamp())
            sent = await self.bot.db.get_sent_event_reminders(event.id, starts_at)
            # armed_since: when the event was made (Discord ids carry their creation time)
            due = rules.due_reminders(
                event.start_time, now, self.reminders, sent, armed_since=discord.utils.snowflake_time(event.id)
            )
            if due.send is not None and not await self.post_reminder(channel, event):
                continue  # Discord hiccup: try again next minute
            if due.done:
                await self.bot.db.mark_event_reminders_sent(event.id, starts_at, list(due.done))

    async def post_reminder(self, channel: discord.TextChannel, event: discord.ScheduledEvent) -> bool:
        pings, pinged = rules.ping_list(await self.fetch_interested(event))
        # The link shows as the event card (title, date, location, Interested button) under the headline
        text = lines.message(lines.reminder(event.name, event.start_time), pings, event.url, lines.NOBODY_YET)
        return await self.post(channel, text, pinged)

    async def post(self, channel: discord.TextChannel, text: str, pinged: list[int]) -> bool:
        """Posts in the alert channel, pinging exactly these people and nobody else. Returns False only when trying
        again later could help (a Discord hiccup); a refused permission is logged once and counts as done."""
        mentions = discord.AllowedMentions(
            everyone=False, roles=False, users=[discord.Object(id=user_id) for user_id in pinged]
        )
        try:
            await channel.send(text, allowed_mentions=mentions)
        except discord.Forbidden:
            self.warn_once(channel.guild, f"Discord won't let me post in #{channel.name}.")
        except discord.HTTPException as error:
            logging.warning("Event alerts: couldn't post in #%s: %s", channel.name, error)
            return False
        return True

    # ---- notices: someone edited or deleted an event in Discord

    @commands.Cog.listener()
    async def on_scheduled_event_update(self, before: discord.ScheduledEvent, _after: discord.ScheduledEvent):
        self.queue_notice(before)

    @commands.Cog.listener()
    async def on_scheduled_event_delete(self, event: discord.ScheduledEvent):
        self.queue_notice(event)

    def queue_notice(self, event: discord.ScheduledEvent) -> None:
        """Remembers how the event looked before the first edit, then (re)starts a short timer: only once the edits
        stop does settle() compare before and after and decide whether it's worth a notice."""
        if event.guild_id not in self.channels:
            return
        pending = self.pending.get(event.id)
        if pending is None:
            interested = set(self.interested.get(event.id, set()))
            pending = PendingNotice(event.guild_id, state_of(event), interested, discord.utils.utcnow())
            self.pending[event.id] = pending
        if pending.timer:
            pending.timer.cancel()
        pending.timer = asyncio.create_task(self.settle_later(event.id))

    async def settle_later(self, event_id: int) -> None:
        await asyncio.sleep(rules.NOTICE_DELAY.total_seconds())  # a newer edit cancels this and starts a new wait
        pending = self.pending.pop(event_id, None)
        if pending is None:
            return
        try:
            await self.settle(event_id, pending)
        except Exception:  # a background task's error would otherwise vanish without a trace
            logging.exception("Event alerts: the notice for event %s failed.", event_id)

    async def settle(self, event_id: int, pending: PendingNotice) -> None:
        guild = self.bot.get_guild(pending.guild_id)
        if guild is None:
            return
        event = guild.get_scheduled_event(event_id)  # None: it was deleted
        if event is None:
            self.interested.pop(event_id, None)
        change = rules.change_worth_a_notice(pending.before, state_of(event) if event else None, pending.since)
        channel = self.alert_channel(guild)
        if change is None or channel is None:
            return

        if change is Change.CANCELLED:
            # Whoever was Interested before the first edit: the event may be gone, so Discord can't be asked
            pings, pinged = rules.ping_list(pending.interested)
            headline = lines.cancelled(pending.before.name, pending.before.start)
            await self.post(channel, lines.message(headline, pings), pinged)
            return

        if change is Change.NEW_PLACE:
            headline = lines.new_place(event.name, event.location or "")
        else:
            # Moved: the notice covers any reminder whose time has already passed for the new start
            now = discord.utils.utcnow()
            starts_at = int(event.start_time.timestamp())
            due = rules.due_reminders(event.start_time, now, self.reminders, set(), armed_since=now)
            if due.done:
                await self.bot.db.mark_event_reminders_sent(event.id, starts_at, list(due.done))
            headline = lines.moved(event.name, event.start_time)
        pings, pinged = rules.ping_list(await self.fetch_interested(event))
        await self.post(channel, lines.message(headline, pings, event.url), pinged)


async def setup(bot):
    await bot.add_cog(EventAlerts(bot))
