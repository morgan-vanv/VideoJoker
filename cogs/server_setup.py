"""/setup: everything a VIP sets up once per server, in one place, hidden from everyone else's / menu.

Morgan (2026-11-16): commands are the nicest way to set things up, but once a thing is set up nobody wants to keep
seeing its command. So every "set it once" command lives here, under one /setup group that Discord only shows to
people who can Manage Server (the server owner can show it to another role in Server Settings → Integrations →
VideoJoker). Every subcommand is VIP-only on top of that, like the old commands were.

    /setup show                                  everything set up in this server, and anything that's wrong
    /setup ladder set | off | tidy               the XP rank ladder              (was /ladder setup, off, tidy)
    /setup voice set | off                       personal voice channels         (was /personalvc setup, off)
    /setup events [channel]                      event reminders                 (was /seteventalerts)
    /setup minecraft marquee | welcome | postcards                               (was /mc marquee, welcome, postcards)
    /setup osrs-webhook                          replace a leaked flexing webhook (was /osrs rotate-webhook)
    /setup people vip | ban | reset | check | vips | banned            (was /grantvipuser, /grantbanuser, ...)

This file only holds the commands. Each one hands the work to the feature's own cog (Ranks, PersonalVC, ...), where
that code has always lived, so moving a command here didn't move or rewrite how it works. Settings are stored where
they always were: nothing needs setting up again.
"""

import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from cogs.permissions import is_vip
from cogs.ranks import MAX_XP
from ranks.ladder import DEFAULT_MIN_XP

FEATURE_NOT_RUNNING = "That feature isn't running right now (its part of the bot didn't load). The log says why."

# /setup show, top to bottom: (field title, the cog that knows about it)
SHOW_ORDER = [
    ("Rank ladder", "Ranks"),
    ("Personal voice channels", "PersonalVC"),
    ("Event reminders", "EventAlerts"),
    ("Minecraft", "Minecraft"),
    ("Old School RuneScape", "Osrs"),
]


@app_commands.guild_only()
# Out of the / menu for everyone without Manage Server. Discord's own setting, so the owner can change who sees it.
@app_commands.default_permissions(manage_guild=True)
class Setup(commands.GroupCog, group_name="setup", group_description="VIP: set the bot up for this server"):
    """/setup: the server's one-time settings, hidden from members"""

    # Subgroups: /setup ladder ..., /setup voice ..., and so on (Discord allows one level of these inside a group)
    ladder = app_commands.Group(name="ladder", description="The XP rank ladder")
    voice = app_commands.Group(name="voice", description="Personal voice channels")
    minecraft = app_commands.Group(name="minecraft", description="Minecraft: the marquee, welcomes and postcards")
    people = app_commands.Group(name="people", description="Who's a VIP and who's banned from the bot")

    def __init__(self, bot):
        logging.info("Setup cog initialized.")
        self.bot = bot

    async def feature(self, interaction: discord.Interaction, cog_name: str) -> Optional[commands.Cog]:
        """The cog that does the work, or None (and a reply saying so) if it didn't load."""
        cog = self.bot.get_cog(cog_name)
        if cog is None:
            await interaction.response.send_message(FEATURE_NOT_RUNNING, ephemeral=True)
        return cog

    # ---- /setup show

    @app_commands.command(name="show", description="VIP: everything set up in this server, and anything that's wrong")
    @is_vip()
    async def show(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        embed = discord.Embed(title=f"⚙️ How the bot is set up in {guild.name}", colour=discord.Colour.dark_gold())
        for title, cog_name in SHOW_ORDER:
            cog = self.bot.get_cog(cog_name)
            if cog is None:
                value = "Not running (its part of the bot didn't load)."
            else:
                value = await cog.setup_summary(guild)  # each feature describes its own settings
            embed.add_field(name=title, value=value[:1024], inline=False)  # Discord: 1024 characters per field
        db = self.bot.db
        embed.add_field(name="People", value=f"VIPs: {len(db.vips)} · Banned: {len(db.banned)}", inline=False)
        embed.set_footer(text="⚠️ marks something that stops a feature working. Change anything with /setup.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ---- /setup ladder

    @ladder.command(name="set", description="VIP: pick the three rank roles and their XP thresholds")
    @app_commands.describe(
        serfs="The first rank, earned with a member's first message",
        swords="The middle rank",
        lords="The top rank",
        swords_xp=f"XP for the middle rank (default: what it is now, or {DEFAULT_MIN_XP[2]})",
        lords_xp=f"XP for the top rank (default: what it is now, or {DEFAULT_MIN_XP[3]})",
    )
    @is_vip()
    # pylint: disable=too-many-arguments, too-many-positional-arguments
    async def ladder_set(
        self,
        interaction: discord.Interaction,
        serfs: discord.Role,
        swords: discord.Role,
        lords: discord.Role,
        swords_xp: Optional[app_commands.Range[int, 2, MAX_XP]] = None,
        lords_xp: Optional[app_commands.Range[int, 2, MAX_XP]] = None,
    ) -> None:
        if cog := await self.feature(interaction, "Ranks"):
            await cog.setup(interaction, serfs, swords, lords, swords_xp, lords_xp)

    @ladder.command(name="off", description="VIP: stop handing out ranks here. Nobody loses a role.")
    @is_vip()
    async def ladder_off(self, interaction: discord.Interaction) -> None:
        if cog := await self.feature(interaction, "Ranks"):
            await cog.off(interaction)

    @ladder.command(name="tidy", description="VIP: one rank each, and enough XP for the rank they wear")
    @is_vip()
    async def ladder_tidy(self, interaction: discord.Interaction) -> None:
        if cog := await self.feature(interaction, "Ranks"):
            await cog.tidy(interaction)

    # ---- /setup voice

    @voice.command(name="set", description="VIP: pick the lobby and the staff role")
    @app_commands.describe(
        hub="The lobby: the voice channel people join to get their own. Must be in a category.",
        staff="Moderators: they can see and join every personal channel, even hidden ones (leave out for none)",
    )
    @is_vip()
    async def voice_set(
        self, interaction: discord.Interaction, hub: discord.VoiceChannel, staff: Optional[discord.Role] = None
    ) -> None:
        if cog := await self.feature(interaction, "PersonalVC"):
            await cog.setup(interaction, hub, staff)

    @voice.command(name="off", description="VIP: no new personal channels. Open ones stay until they empty.")
    @is_vip()
    async def voice_off(self, interaction: discord.Interaction) -> None:
        if cog := await self.feature(interaction, "PersonalVC"):
            await cog.off(interaction)

    # ---- /setup events

    @app_commands.command(name="events", description="VIP: where event reminders go (leave empty to switch them off)")
    @app_commands.describe(channel="Where reminders and changes to this server's events go (empty = alerts off)")
    @is_vip()
    async def events(self, interaction: discord.Interaction, channel: Optional[discord.TextChannel] = None) -> None:
        if cog := await self.feature(interaction, "EventAlerts"):
            await cog.set_event_alerts(interaction, channel)

    # ---- /setup minecraft

    @minecraft.command(name="marquee", description="VIP: keep a Minecraft status card in a channel (empty = off)")
    @app_commands.describe(channel="Where the card goes; leave empty to switch it off")
    @is_vip()
    async def minecraft_marquee(
        self, interaction: discord.Interaction, channel: Optional[discord.TextChannel] = None
    ) -> None:
        if cog := await self.feature(interaction, "Minecraft"):
            await cog.set_marquee(interaction, channel)

    @minecraft.command(name="welcome", description="VIP: welcome people who get the Minecraft role (empty = off)")
    @app_commands.describe(
        channel="Where the welcome is posted; leave empty to switch welcomes off",
        role="The role to watch for (the onboarding question's Minecraft role)",
    )
    @is_vip()
    async def minecraft_welcome(
        self,
        interaction: discord.Interaction,
        channel: Optional[discord.TextChannel] = None,
        role: Optional[discord.Role] = None,
    ) -> None:
        if cog := await self.feature(interaction, "Minecraft"):
            await cog.set_welcome(interaction, channel, role)

    @minecraft.command(name="postcards", description="VIP: post Minecraft postcards in a channel (empty = off)")
    @app_commands.describe(channel="Where postcards go; leave empty to switch them off")
    @is_vip()
    async def minecraft_postcards(
        self, interaction: discord.Interaction, channel: Optional[discord.TextChannel] = None
    ) -> None:
        if cog := await self.feature(interaction, "Minecraft"):
            await cog.set_postcards(interaction, channel)

    # ---- /setup osrs-webhook

    @app_commands.command(name="osrs-webhook", description="VIP: replace a leaked OSRS flexing webhook")
    @is_vip()
    async def osrs_webhook(self, interaction: discord.Interaction) -> None:
        if cog := await self.feature(interaction, "Osrs"):
            await cog.rotate_webhook(interaction)

    # ---- /setup people (Morgan's permission commands, from cogs/permissions.py)

    @people.command(name="vip", description="VIP: make someone a VIP")
    @app_commands.describe(user="Who gets VIP")
    @is_vip()
    async def people_vip(self, interaction: discord.Interaction, user: discord.User) -> None:
        if cog := await self.feature(interaction, "Permissions"):
            await cog.grant_vip_user(interaction, user)

    @people.command(name="ban", description="VIP: ban someone from using the bot")
    @app_commands.describe(user="Who gets banned from the bot")
    @is_vip()
    async def people_ban(self, interaction: discord.Interaction, user: discord.User) -> None:
        if cog := await self.feature(interaction, "Permissions"):
            await cog.grant_ban_user(interaction, user)

    @people.command(name="reset", description="VIP: take away someone's VIP or ban")
    @app_commands.describe(user="Whose VIP or ban goes")
    @is_vip()
    async def people_reset(self, interaction: discord.Interaction, user: discord.User) -> None:
        if cog := await self.feature(interaction, "Permissions"):
            await cog.reset_permissions(interaction, user)

    @people.command(name="check", description="VIP: is someone a VIP, banned, or neither?")
    @app_commands.describe(user="Who to check")
    @is_vip()
    async def people_check(self, interaction: discord.Interaction, user: discord.User) -> None:
        if cog := await self.feature(interaction, "Permissions"):
            await cog.check_permissions(interaction, user)

    @people.command(name="vips", description="VIP: everyone with VIP")
    @is_vip()
    async def people_vips(self, interaction: discord.Interaction) -> None:
        if cog := await self.feature(interaction, "Permissions"):
            await cog.list_vip_users(interaction)

    @people.command(name="banned", description="VIP: everyone banned from the bot")
    @is_vip()
    async def people_banned(self, interaction: discord.Interaction) -> None:
        if cog := await self.feature(interaction, "Permissions"):
            await cog.list_banned_users(interaction)


async def setup(bot):
    await bot.add_cog(Setup(bot))
