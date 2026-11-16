"""The /mc commands: link your Minecraft accounts, see who plays what, and check on the server.

Design and the why behind it: docs/minecraft-design.md. The pieces live in minecraft/ (name rules, the account
lookups, the server-list ping, buttons, the VJ's lines); this file turns slash commands and Discord events into
calls to them. Three things run without anyone typing a command:
- the marquee: a status card the VJ keeps up to date in one channel (set with /mc marquee);
- the welcome: when someone gets the Minecraft role from onboarding, the VJ greets them once (set with /mc welcome);
- the "Get me in the game" button on both, which keeps working across restarts.

Part 1 only reads public things (the server's address, Mojang, GeyserMC). Part 2 talks to the booth, a small
service next to the Minecraft servers (booth/, minecraft/booth.py), when BOOTH_URL and BOOTH_TOKEN are set:
/mc shout, postcards, players per mode, and telling the booth who's linked so its "join our Discord" nudge leaves
them alone. No new permissions beyond View Channel, Send Messages and Embed Links in the channels it posts in.
"""

import asyncio
import logging
import os
import time
from datetime import datetime, timezone
from typing import Optional

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks

from cogs.permissions import is_vip
from core.database import McAccount, McSettings
from minecraft import lines, lookup, postcards
from minecraft.accounts import clean_name
from minecraft.booth import BoothClient, BoothUnavailable, ModeStatus
from minecraft.ping import PingFailed, ServerStatus, ping
from minecraft.rules import should_welcome, status_line
from minecraft.server import ADDRESS, JAVA_PORT
from minecraft.shout import MAX_LENGTH, SHOUT_COST, Cooldowns
from minecraft.ui import AfterLinkView, StartView

EMBED_COLOUR = discord.Colour.from_str("#5B8731")  # grass-block green
MARQUEE_MINUTES = 2
POSTCARD_SECONDS = 15  # how often the bot asks the booth for new postcards
LINKED_SYNC_MINUTES = 10  # the booth forgets on restart, so the bot repeats who's linked this often
# What the VJ needs in the marquee and welcome channels: discord.py's name for each permission, then Discord's
NEEDED = {"view_channel": "View Channel", "send_messages": "Send Messages", "embed_links": "Embed Links"}
EDITION_CHOICES = [
    app_commands.Choice(name=lines.EDITION_NAMES["java"], value="java"),
    app_commands.Choice(name=lines.EDITION_NAMES["bedrock"], value="bedrock"),
]


def missing(channel: discord.abc.GuildChannel) -> list[str]:
    """Which of the NEEDED permissions the VJ doesn't have in this channel, as Discord's UI names them."""
    have = channel.permissions_for(channel.guild.me)
    return [label for name, label in NEEDED.items() if not getattr(have, name)]


def shown(account: McAccount) -> str:
    """An account's name as shown in messages: markdown-safe, so "__Steve__" doesn't turn into underlined text."""
    return discord.utils.escape_markdown(account.name)


@app_commands.guild_only()
class Minecraft(  # pylint: disable=too-many-public-methods,too-many-instance-attributes  # commands are methods
    commands.GroupCog, group_name="mc", group_description="Link your Minecraft accounts, see who's on."
):
    """Minecraft: account linking, the server's status, and a welcome for new players"""

    def __init__(self, bot):
        logging.info("Minecraft cog initialized.")
        self.bot = bot
        self.session: Optional[aiohttp.ClientSession] = None
        self.settings: dict[int, McSettings] = {}
        self.warned: set[tuple[int, str]] = set()  # (server, problem) already logged, so the log isn't flooded
        # Part 2, the booth: None when BOOTH_URL / BOOTH_TOKEN aren't set (those features are off then)
        self.booth: Optional[BoothClient] = None
        self.cooldowns = Cooldowns()
        self.postcard_channels: dict[int, int] = {}  # server id → postcards channel id
        self.postcard_boot: Optional[str] = None  # which run of the booth our event numbers belong to
        self.postcard_after = 0  # the last event number we've posted
        self.background: set[asyncio.Task] = set()

    async def cog_load(self):
        self.session = aiohttp.ClientSession()  # one web session for the cog's whole life, closed on shutdown
        self.settings = await self.bot.db.get_mc_settings()
        self.postcard_channels = await self.bot.db.get_mc_postcards()
        url, token = os.getenv("BOOTH_URL", "").strip(), os.getenv("BOOTH_TOKEN", "").strip()
        if url and token:
            self.booth = BoothClient(self.session, url, token)
            logging.info("Minecraft booth: on.")
        else:
            # Contract rule 7: a missing optional setting switches its feature off, with a warning, never a crash
            logging.warning("Minecraft booth off (BOOTH_URL / BOOTH_TOKEN not set): no /mc shout or postcards.")
        self.bot.add_view(StartView(self))  # so "Get me in the game" works on messages from before a restart
        self.marquee.start()
        self.linked_sync.start()
        self.postcard_check.start()

    async def cog_unload(self):
        self.marquee.cancel()
        self.linked_sync.cancel()
        self.postcard_check.cancel()
        if self.session:
            await self.session.close()

    def warn_once(self, guild: discord.Guild, problem: str) -> None:
        if (guild.id, problem) not in self.warned:
            self.warned.add((guild.id, problem))
            logging.warning("Minecraft in %s: %s", guild.name, problem)

    # ---- linking (the command, and the pop-up after "Get me in the game")

    async def link(self, interaction: discord.Interaction, raw_name: str, edition: str) -> None:
        """Checks the name, looks the account up, links it, then shows the join card and "where to first?"."""
        name = clean_name(raw_name, edition)
        if name is None:
            text = lines.INVALID_NAME[edition].format(name=discord.utils.escape_markdown(raw_name.strip()))
            await interaction.response.send_message(text, ephemeral=True)
            return

        # Asking Mojang or GeyserMC can take a second, and Discord wants an answer within 3: defer first
        await interaction.response.defer(ephemeral=True)
        try:
            profile = await lookup.find(self.session, name, edition)
        except lookup.LookupUnavailable:
            await interaction.edit_original_response(content=lines.LOOKUP_DOWN.format(service=lines.SERVICES[edition]))
            return
        if profile is None:
            text = lines.NOT_FOUND[edition].format(name=discord.utils.escape_markdown(name))
            await interaction.edit_original_response(content=text)
            return

        account_name = discord.utils.escape_markdown(profile.name)
        edition_name = lines.EDITION_NAMES[edition]
        owner = await self.bot.db.add_mc_account(interaction.user.id, edition, profile.uuid, profile.name)
        if owner is not None and owner != interaction.user.id:
            # <@id> shows as their name; it doesn't ping anyone because the message is ephemeral
            text = lines.TAKEN.format(name=account_name, edition=edition_name, owner=f"<@{owner}>")
            await interaction.edit_original_response(content=text)
            return

        if owner == interaction.user.id:
            first_line = lines.ALREADY_YOURS.format(name=account_name, edition=edition_name)
        else:
            accounts = await self.bot.db.get_mc_accounts(interaction.user.id)
            is_default = any(a.uuid == profile.uuid and a.is_default for a in accounts)
            first_line = lines.LINKED.format(name=account_name, edition=edition_name)
            first_line += lines.LINKED_DEFAULT if is_default else ""
        self.linked_changed()
        view = AfterLinkView(intro=f"{first_line}\n{lines.JOIN[edition]}")
        view.message_owner = interaction
        await interaction.edit_original_response(content=view.text(), view=view)

    # ---- the status card (/mc status and the marquee share it)

    async def check_server(self) -> Optional[ServerStatus]:
        """The server's status, or None if it isn't answering."""
        try:
            return await ping(ADDRESS, JAVA_PORT)
        except PingFailed as error:
            logging.debug("Minecraft server-list ping failed: %s", error)
            return None

    async def check_modes(self) -> Optional[dict[str, ModeStatus]]:
        """Players per mode and which modes are asleep, from the booth; None if there's no booth or it didn't answer."""
        if self.booth is None:
            return None
        try:
            return await self.booth.status()
        except BoothUnavailable as error:
            logging.debug("The booth didn't answer /status: %s", error)
            return None

    @staticmethod
    def status_embed(status: Optional[ServerStatus], modes: Optional[dict[str, ModeStatus]] = None) -> discord.Embed:
        embed = discord.Embed(title=lines.STATUS_TITLE, description=status_line(status), colour=EMBED_COLOUR)
        if status is not None and modes:
            rows = [
                (lines.STATUS_MODE_AWAKE if mode.awake else lines.STATUS_MODE_ASLEEP).format(
                    mode=lines.MODE_NAMES.get(name, name.title()), online=mode.online
                )
                for name, mode in modes.items()
            ]
            embed.add_field(name=lines.STATUS_PER_MODE_NAME, value="\n".join(rows), inline=False)
        embed.add_field(name=lines.STATUS_HOW_NAME, value=lines.STATUS_HOW, inline=False)
        embed.add_field(name=lines.STATUS_MODES_NAME, value=lines.STATUS_MODES, inline=False)
        embed.set_footer(text=lines.STATUS_FOOTER)
        embed.timestamp = datetime.now(timezone.utc)  # Discord shows it in each reader's own time zone
        return embed

    @tasks.loop(minutes=MARQUEE_MINUTES)
    async def marquee(self):
        # A loop that raises stops for good, so catch everything (house rule, see the heartbeat and event alerts)
        try:
            wanted = [s for s in self.settings.values() if s.marquee_channel_id]
            if not wanted:
                return
            embed = self.status_embed(await self.check_server(), await self.check_modes())
            for settings in wanted:
                await self.update_marquee(settings, embed)
        except Exception:  # pylint: disable=broad-exception-caught
            logging.exception("The Minecraft marquee update failed; trying again next time.")

    @marquee.before_loop
    async def before_marquee(self):
        await self.bot.wait_until_ready()

    async def update_marquee(self, settings: McSettings, embed: discord.Embed) -> None:
        """Edits the marquee card; if it was deleted, posts a fresh one and remembers it."""
        guild = self.bot.get_guild(settings.guild_id)
        if guild is None:
            return
        channel = guild.get_channel(settings.marquee_channel_id)
        if not isinstance(channel, discord.TextChannel):
            self.warn_once(guild, "the marquee channel is gone (deleted?). Run /mc marquee again.")
            return
        try:
            if settings.marquee_message_id:
                # A "partial message" is just an id we can act on, without fetching the whole message first
                await channel.get_partial_message(settings.marquee_message_id).edit(embed=embed, view=StartView(self))
                return
        except discord.NotFound:
            pass  # someone deleted the card: post a new one below
        except discord.Forbidden:
            self.warn_once(guild, f"can't edit the marquee in #{channel.name}.")
            return
        try:
            message = await channel.send(embed=embed, view=StartView(self))
        except discord.Forbidden:
            self.warn_once(guild, f"can't post the marquee in #{channel.name}.")
            return
        await self.save_marquee(guild.id, channel.id, message.id)

    async def save_marquee(self, guild_id: int, channel_id: Optional[int], message_id: Optional[int]) -> None:
        await self.bot.db.set_mc_marquee(guild_id, channel_id, message_id)
        old = self.settings.get(guild_id, McSettings(guild_id))
        self.settings[guild_id] = old._replace(marquee_channel_id=channel_id, marquee_message_id=message_id)

    # ---- the welcome

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        settings = self.settings.get(after.guild.id)
        if settings is None or not settings.welcome_channel_id or not settings.welcome_role_id or after.bot:
            return
        if not should_welcome(
            settings.welcome_role_id,
            [role.id for role in before.roles],
            [role.id for role in after.roles],
            bool(before.pending),
            bool(after.pending),
        ):
            return
        channel = after.guild.get_channel(settings.welcome_channel_id)
        if not isinstance(channel, discord.TextChannel):
            self.warn_once(after.guild, "the welcome channel is gone (deleted?). Run /mc welcome again.")
            return
        if not await self.bot.db.mark_mc_welcomed(after.guild.id, after.id):
            return  # welcomed before (they had the role once already)
        try:
            await channel.send(
                lines.WELCOME.format(member=after.mention, address=ADDRESS),
                view=StartView(self),
                allowed_mentions=discord.AllowedMentions(users=[after]),  # ping exactly the newcomer
            )
        except discord.Forbidden:
            self.warn_once(after.guild, f"can't post welcomes in #{channel.name}.")

    # ---- commands

    @app_commands.command(name="register", description="Link your Minecraft account (Java or Bedrock) to your Discord")
    @app_commands.describe(name="Your Java username or Xbox gamertag", edition="Which Minecraft you play")
    @app_commands.choices(edition=EDITION_CHOICES)
    async def register(self, interaction: discord.Interaction, name: str, edition: app_commands.Choice[str]) -> None:
        await self.link(interaction, name, edition.value)

    def accounts_embed(self, member: discord.abc.User, accounts: list[McAccount]) -> discord.Embed:
        rows = [
            f"**{shown(account)}** · {lines.EDITION_NAMES[account.edition]}" + (" ⭐" if account.is_default else "")
            for account in accounts
        ]
        embed = discord.Embed(
            title=lines.ACCOUNTS_TITLE.format(member=member.display_name),
            description="\n".join(rows),
            colour=EMBED_COLOUR,
        )
        embed.set_footer(text=lines.ACCOUNTS_LEGEND)
        return embed

    @app_commands.command(name="accounts", description="Shows the Minecraft accounts linked to your Discord")
    async def accounts(self, interaction: discord.Interaction) -> None:
        accounts = await self.bot.db.get_mc_accounts(interaction.user.id)
        if not accounts:
            await interaction.response.send_message(lines.NO_ACCOUNTS, ephemeral=True)
            return
        await interaction.response.send_message(embed=self.accounts_embed(interaction.user, accounts), ephemeral=True)

    @app_commands.command(name="whois", description="Shows which Minecraft accounts a server member plays")
    @app_commands.describe(member="The person to look up")
    async def whois(self, interaction: discord.Interaction, member: discord.Member) -> None:
        accounts = await self.bot.db.get_mc_accounts(member.id)
        if not accounts:
            await interaction.response.send_message(
                lines.WHOIS_NOBODY.format(member=member.mention),
                allowed_mentions=discord.AllowedMentions.none(),  # show the name, but don't ping them
            )
            return
        await interaction.response.send_message(embed=self.accounts_embed(member, accounts))

    @app_commands.command(name="who", description="Which server member plays this Minecraft name?")
    @app_commands.describe(name="A Java username or Xbox gamertag")
    async def who(self, interaction: discord.Interaction, name: str) -> None:
        typed = name.strip().removeprefix(".")  # Bedrock players show up in game as ".Gamertag"
        found = await self.bot.db.find_mc_accounts_by_name(typed)
        if not found:
            text = lines.WHO_NOBODY.format(name=discord.utils.escape_markdown(typed))
        else:
            text = "\n".join(
                lines.WHO_FOUND.format(
                    name=shown(account), edition=lines.EDITION_NAMES[account.edition], member=f"<@{account.discord_id}>"
                )
                for account in found
            )
        await interaction.response.send_message(text, allowed_mentions=discord.AllowedMentions.none())

    async def your_account(self, user_id: int, typed: str) -> Optional[McAccount]:
        """One of your accounts, by what autocomplete filled in (its UUID) or a name you typed yourself."""
        for account in await self.bot.db.get_mc_accounts(user_id):
            if typed in (account.uuid, account.name) or typed.lower() == account.name.lower():
                return account
        return None

    @app_commands.command(name="default", description="Picks which of your Minecraft accounts is your main one")
    @app_commands.describe(account="One of your linked accounts")
    async def default(self, interaction: discord.Interaction, account: str) -> None:
        found = await self.your_account(interaction.user.id, account)
        if found is None or not await self.bot.db.set_default_mc_account(interaction.user.id, found.uuid):
            text = lines.NOT_YOURS.format(name=discord.utils.escape_markdown(account))
        else:
            text = lines.NEW_DEFAULT.format(name=shown(found))
        await interaction.response.send_message(text, ephemeral=True)

    @app_commands.command(name="remove", description="Unlinks one of your Minecraft accounts")
    @app_commands.describe(account="One of your linked accounts")
    async def remove(self, interaction: discord.Interaction, account: str) -> None:
        found = await self.your_account(interaction.user.id, account)
        if found is None or not await self.bot.db.remove_mc_account(interaction.user.id, found.uuid):
            text = lines.NOT_YOURS.format(name=discord.utils.escape_markdown(account))
        else:
            text = lines.REMOVED.format(name=shown(found))
            self.linked_changed()
        await interaction.response.send_message(text, ephemeral=True)

    # Autocomplete shows your accounts by name, and hands the command the account's UUID: names can repeat (a Java
    # and a Bedrock account called the same), UUIDs can't
    @default.autocomplete("account")
    @remove.autocomplete("account")
    async def your_accounts(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        accounts = await self.bot.db.get_mc_accounts(interaction.user.id)
        return [
            app_commands.Choice(name=f"{a.name} ({lines.EDITION_NAMES[a.edition]})", value=a.uuid)
            for a in accounts
            if current.lower() in a.name.lower()
        ][:25]

    @app_commands.command(name="status", description="Is the Minecraft server up, and how many are on?")
    async def status(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()  # public: "who's on?" is a conversation starter
        embed = self.status_embed(await self.check_server(), await self.check_modes())
        await interaction.edit_original_response(embed=embed, view=StartView(self))

    @app_commands.command(name="marquee", description="VIP: keep a Minecraft status card in a channel (empty = off)")
    @app_commands.describe(channel="Where the card goes; leave empty to switch it off")
    @is_vip()
    async def set_marquee(self, interaction: discord.Interaction, channel: Optional[discord.TextChannel] = None):
        if channel is None:
            await self.save_marquee(interaction.guild_id, None, None)
            await interaction.response.send_message(lines.MARQUEE_OFF, ephemeral=True)
            return
        if lacking := missing(channel):
            text = lines.NO_PERMISSION.format(missing=", ".join(lacking), channel=channel.mention)
            await interaction.response.send_message(text, ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        message = await channel.send(embed=self.status_embed(await self.check_server()), view=StartView(self))
        await self.save_marquee(interaction.guild_id, channel.id, message.id)
        logging.info("Minecraft marquee set up in %s by %s", interaction.guild.name, interaction.user.name)
        await interaction.edit_original_response(content=lines.MARQUEE_ON.format(channel=channel.mention))

    @app_commands.command(name="welcome", description="VIP: welcome people who get the Minecraft role (empty = off)")
    @app_commands.describe(
        channel="Where the welcome is posted; leave empty to switch welcomes off",
        role="The role to watch for (the onboarding question's Minecraft role)",
    )
    @is_vip()
    async def set_welcome(
        self,
        interaction: discord.Interaction,
        channel: Optional[discord.TextChannel] = None,
        role: Optional[discord.Role] = None,
    ):
        if channel is None:
            await self.save_welcome(interaction.guild_id, None, None)
            await interaction.response.send_message(lines.WELCOME_OFF, ephemeral=True)
            return
        if role is None:
            await interaction.response.send_message(lines.WELCOME_NEEDS_ROLE, ephemeral=True)
            return
        if lacking := missing(channel):
            text = lines.NO_PERMISSION.format(missing=", ".join(lacking), channel=channel.mention)
            await interaction.response.send_message(text, ephemeral=True)
            return
        await self.save_welcome(interaction.guild_id, channel.id, role.id)
        logging.info("Minecraft welcomes set up in %s by %s", interaction.guild.name, interaction.user.name)
        await interaction.response.send_message(
            lines.WELCOME_ON.format(role=role.mention, channel=channel.mention),
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    async def save_welcome(self, guild_id: int, channel_id: Optional[int], role_id: Optional[int]) -> None:
        await self.bot.db.set_mc_welcome(guild_id, channel_id, role_id)
        old = self.settings.get(guild_id, McSettings(guild_id))
        self.settings[guild_id] = old._replace(welcome_channel_id=channel_id, welcome_role_id=role_id)

    # ---- part 2: the booth

    def linked_changed(self) -> None:
        """Someone linked or unlinked an account: tell the booth soon, without making them wait for it."""
        if self.booth is not None:
            # Keep a reference until it's done: asyncio only holds tasks weakly, so an unreferenced one can vanish
            task = asyncio.create_task(self.push_linked())
            self.background.add(task)
            task.add_done_callback(self.background.discard)

    async def push_linked(self) -> None:
        try:
            await self.booth.put_linked(await self.bot.db.get_all_mc_uuids())
        except BoothUnavailable as error:
            logging.debug("Couldn't tell the booth who's linked: %s", error)

    @tasks.loop(minutes=LINKED_SYNC_MINUTES)
    async def linked_sync(self):
        try:
            if self.booth is not None:
                await self.push_linked()
        except Exception:  # pylint: disable=broad-exception-caught
            logging.exception("Telling the booth who's linked failed; trying again next time.")

    @linked_sync.before_loop
    async def before_linked_sync(self):
        await self.bot.wait_until_ready()

    @tasks.loop(seconds=POSTCARD_SECONDS)
    async def postcard_check(self):
        try:
            if self.booth is not None and self.postcard_channels:
                await self.deliver_postcards()
        except Exception:  # pylint: disable=broad-exception-caught
            logging.exception("Postcards failed; trying again next time.")

    @postcard_check.before_loop
    async def before_postcard_check(self):
        await self.bot.wait_until_ready()

    async def deliver_postcards(self) -> None:
        """Asks the booth what happened since the last postcard, and posts it."""
        try:
            batch = await self.booth.postcards(self.postcard_after)
            if batch.boot != self.postcard_boot:
                if self.postcard_boot is None:
                    # The bot just started: skip what happened before (we may have posted it already)
                    self.postcard_boot, self.postcard_after = batch.boot, batch.latest
                    return
                # The booth restarted: its numbers start over, so everything it has is new to us
                self.postcard_boot = batch.boot
                batch = await self.booth.postcards(0)
        except BoothUnavailable as error:
            logging.debug("The booth didn't answer /events: %s", error)
            return
        for event in batch.events:
            self.postcard_after = max(self.postcard_after, int(event.get("id", 0)))
            text = await self.postcard_text(event)
            if text:
                await self.post_postcard(text)

    async def postcard_text(self, event: dict) -> Optional[str]:
        name = str(event.get("name", ""))
        if event.get("kind") == "join" and not await self.bot.db.mark_mc_player_seen(name.lower()):
            return None  # only a player's first time on the network gets a postcard
        edition, stored = postcards.account_name(name)
        owners = sorted(
            {a.discord_id for a in await self.bot.db.find_mc_accounts_by_name(stored) if a.edition == edition}
        )
        return postcards.text_for(event, owners)

    async def post_postcard(self, text: str) -> None:
        for guild_id, channel_id in self.postcard_channels.items():
            guild = self.bot.get_guild(guild_id)
            channel = guild.get_channel(channel_id) if guild else None
            if not isinstance(channel, discord.TextChannel):
                if guild:
                    self.warn_once(guild, "the postcards channel is gone (deleted?). Run /mc postcards again.")
                continue
            try:
                # Names a linked member without pinging them: postcards are for reading, not for buzzing phones
                await channel.send(text, allowed_mentions=discord.AllowedMentions.none())
            except discord.Forbidden:
                self.warn_once(guild, f"can't post postcards in #{channel.name}.")

    @app_commands.command(name="shout", description="Shout a message into the Minecraft server's chat (costs USh)")
    @app_commands.describe(message="What everyone in game will see, after [Discord] and your name")
    async def shout(self, interaction: discord.Interaction, message: app_commands.Range[str, 1, MAX_LENGTH]) -> None:
        if self.booth is None:
            await interaction.response.send_message(lines.SHOUT_OFF, ephemeral=True)
            return
        if not " ".join(message.split()):
            await interaction.response.send_message(lines.SHOUT_EMPTY, ephemeral=True)
            return
        user = interaction.user
        now = time.time()
        if wait := self.cooldowns.check(user.id, now):
            template = lines.SHOUT_WAIT_EVERYONE if wait.everyone else lines.SHOUT_WAIT
            when = discord.utils.format_dt(datetime.fromtimestamp(wait.until, timezone.utc), "R")
            await interaction.response.send_message(template.format(when=when), ephemeral=True)
            return

        free = user.id in self.bot.db.vips
        if not free and not await self.bot.db.move_ush_with_bank(
            user.id, SHOUT_COST, "shout", True, interaction.guild_id
        ):
            balance = await self.bot.db.get_balance(user.id)
            await interaction.response.send_message(
                lines.SHOUT_BROKE.format(cost=SHOUT_COST, balance=balance), ephemeral=True
            )
            return
        # Paid (or free): from here, anything that stops the shout gives the USh back
        self.cooldowns.shouted(user.id, now)
        await interaction.response.defer()
        try:
            result = await self.booth.shout(user.display_name, message)
        except BoothUnavailable:
            result = None
        if not result or not result.heard:
            if not free:
                await self.bot.db.move_ush_with_bank(
                    user.id, SHOUT_COST, "shout refund", False, interaction.guild_id, lines.SHOUT_REFUND_NOTE
                )
            self.cooldowns.last_by_person.pop(user.id, None)  # it didn't happen, so it doesn't count
            await interaction.edit_original_response(content=lines.SHOUT_NOBODY if result else lines.SHOUT_FAILED)
            return

        modes = ", ".join(lines.MODE_NAMES.get(name, name.title()) for name in result.heard)
        text = lines.SHOUT_DONE.format(member=user.mention, modes=modes, text=discord.utils.escape_markdown(message))
        if result.asleep:
            text += lines.SHOUT_ASLEEP.format(
                modes=", ".join(lines.MODE_NAMES.get(n, n.title()) for n in result.asleep)
            )
        text += lines.SHOUT_FREE if free else lines.SHOUT_PAID.format(cost=SHOUT_COST)
        await interaction.edit_original_response(content=text, allowed_mentions=discord.AllowedMentions.none())

    @app_commands.command(name="postcards", description="VIP: post Minecraft postcards in a channel (empty = off)")
    @app_commands.describe(channel="Where postcards go; leave empty to switch them off")
    @is_vip()
    async def set_postcards(self, interaction: discord.Interaction, channel: Optional[discord.TextChannel] = None):
        if channel is None:
            await self.bot.db.set_mc_postcards(interaction.guild_id, None)
            self.postcard_channels.pop(interaction.guild_id, None)
            await interaction.response.send_message(lines.POSTCARDS_OFF, ephemeral=True)
            return
        if lacking := missing(channel):
            text = lines.NO_PERMISSION.format(missing=", ".join(lacking), channel=channel.mention)
            await interaction.response.send_message(text, ephemeral=True)
            return
        await self.bot.db.set_mc_postcards(interaction.guild_id, channel.id)
        self.postcard_channels[interaction.guild_id] = channel.id
        logging.info("Minecraft postcards set up in %s by %s", interaction.guild.name, interaction.user.name)
        text = lines.POSTCARDS_ON.format(channel=channel.mention)
        await interaction.response.send_message(text + ("" if self.booth else lines.POSTCARDS_NO_BOOTH), ephemeral=True)


async def setup(bot):
    await bot.add_cog(Minecraft(bot))
