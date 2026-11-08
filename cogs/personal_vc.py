"""Personal voice channels: join the lobby and the VJ hands you your own channel. Replaces the TempVoice bot.

The rules (names, the three modes as permission overwrites, cooldown, when to delete) live in personal_vc/rules.py
and are tested there. The panel's buttons are in personal_vc/ui.py and every line the VJ says is in
personal_vc/lines.py. This file is the Discord side: it listens to people moving between voice channels, makes and
deletes channels, and changes their permissions.

Needs, on the server: a category (e.g. "personal channels") holding the lobby voice channel. The controls are
posted in each new channel's own chat, so there's no separate panel channel. In that category only, the bot needs
Manage Channels and Move Members (and Manage Roles, View Channel, Connect and Send Messages, which it normally has
server-wide). /personalvc setup says what's missing.
"""

import asyncio
import logging
import time
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from cogs.permissions import is_vip
from core.database import PersonalVcConfig
from personal_vc import lines, rules
from personal_vc.rules import MAX_GUESTS, Mode
from personal_vc.ui import ControlPanel, LetInPicker, Picker, RemovePicker

EMBED_COLOUR = discord.Colour.dark_teal()

# What the bot needs, and where. The names are discord.py's names for each permission, then how Discord's UI says it.
CATEGORY_PERMISSIONS = {
    "view_channel": "View Channel",
    "connect": "Connect",
    "manage_channels": "Manage Channels",  # make and delete the personal channels
    "move_members": "Move Members",  # move people from the lobby into their channel
    "manage_roles": "Manage Roles",  # change a channel's permissions (Discord calls it Manage Permissions there)
    "send_messages": "Send Messages",  # post the welcome and the buttons in each new channel's chat
}


def missing(channel: discord.abc.GuildChannel, needed: dict[str, str]) -> list[str]:
    """Which of these permissions the bot doesn't have in this channel (or category), as Discord's UI names them."""
    have = channel.permissions_for(channel.guild.me)
    return [label for name, label in needed.items() if not getattr(have, name)]


def setup_problems(guild: discord.Guild, config: PersonalVcConfig) -> list[str]:
    """What stops personal channels from working in this server, in plain words (empty = all good)."""
    problems = []
    hub = guild.get_channel(config.hub_channel_id)
    if not isinstance(hub, discord.VoiceChannel):
        problems.append("The lobby voice channel is gone (deleted?). Run `/personalvc setup` again.")
    elif hub.category is None:
        problems.append(f"The lobby '{hub.name}' isn't in a category any more. Move it back, or run setup again.")
    elif needs := missing(hub.category, CATEGORY_PERMISSIONS):
        problems.append(f"I need **{', '.join(needs)}** in the '{hub.category.name}' category.")
    return problems


def humans_in(channel: discord.VoiceChannel) -> list[discord.Member]:
    return [member for member in channel.members if not member.bot]


def copy_overwrite(overwrite: Optional[discord.PermissionOverwrite]) -> discord.PermissionOverwrite:
    """A separate copy, so changing it can't change the category's own overwrite by accident."""
    if overwrite is None:
        return discord.PermissionOverwrite()
    return discord.PermissionOverwrite.from_pair(*overwrite.pair())


def build_overwrites(
    channel: discord.VoiceChannel, mode: Mode, let_in: set[int]
) -> dict[discord.Role | discord.Member | discord.Object, discord.PermissionOverwrite]:
    """The channel's whole set of overwrites for this mode: the category's, with the mode's layer on top."""
    guild = channel.guild
    base = dict(channel.category.overwrites) if channel.category else {}
    targets = {target.id: target for target in base}
    result = {target.id: copy_overwrite(overwrite) for target, overwrite in base.items()}

    for target_id, changes in rules.mode_layer(mode, guild.id, list(targets), let_in).items():
        if target_id not in targets:
            # Not in the category: find the role or member it is (get_role also finds @everyone)
            target = guild.get_role(target_id)
            if target is None:
                target = guild.get_member(target_id)
            if target is None:
                continue  # a guest who left the server, or a deleted staff role: nothing to set
            targets[target_id] = target
        overwrite = result.get(target_id, discord.PermissionOverwrite())
        overwrite.update(**changes)
        result[target_id] = overwrite

    # An overwrite with everything neutral does nothing, so leave it out instead of sending it
    return {targets[target_id]: overwrite for target_id, overwrite in result.items() if not overwrite.is_empty()}


# One feature with listeners, panel buttons and commands, kept together on purpose (like Database in core/)
@app_commands.guild_only()
class PersonalVC(  # pylint: disable=too-many-public-methods
    commands.GroupCog, group_name="personalvc", group_description="Personal voice channels: join the lobby, get one."
):
    """Personal voice channels: join the lobby to get your own, with a panel to lock it, hide it and let people in"""

    def __init__(self, bot):
        logging.info("Personal voice channels cog initialized.")
        self.bot = bot
        # Every server's setup, kept in memory: it's read on every voice move, so no database trip each time
        self.configs: dict[int, PersonalVcConfig] = {}
        # (server id, problem) pairs already in the log, so a missing permission is logged once, not every join
        self.warned: set[tuple[int, str]] = set()
        # (server id, member id) -> when we last made them a channel (time.monotonic()), for the cooldown
        self.last_created: dict[tuple[int, int], float] = {}
        # (server id, member id) pairs we're making a channel for right now, so two events can't make two
        self.busy: set[tuple[int, int]] = set()
        self.checked_on_ready = False
        self.panel = self.new_panel()

    def new_panel(self) -> ControlPanel:
        return ControlPanel(self.on_mode, self.on_let_in, self.on_remove)

    async def cog_load(self):
        # Persistent view: from now on, every panel button on every message (old ones too) reaches this cog.
        # See ControlPanel in personal_vc/ui.py for why this is needed.
        self.bot.add_view(self.panel)
        self.configs = {config.guild_id: config for config in await self.bot.db.get_personal_vc_configs()}
        if self.configs:
            logging.info("Personal voice channels: on in %d server(s).", len(self.configs))
        else:
            # Hosting contract: a feature with nothing set up switches off and says so, the bot still starts
            logging.warning("Personal voice channels: off (no server has run /personalvc setup yet).")

    async def cog_unload(self):
        self.panel.stop()  # stops the persistent view listening, so a reloaded cog doesn't answer twice

    def warn_once(self, guild: discord.Guild, problem: str) -> None:
        if (guild.id, problem) in self.warned:
            return
        self.warned.add((guild.id, problem))
        logging.warning("Personal voice channels in '%s': %s", guild.name, problem)

    # ---- startup tidy-up

    @commands.Cog.listener()
    async def on_ready(self):
        # on_ready runs again after every reconnect; tidying once per start is enough
        if self.checked_on_ready:
            return
        self.checked_on_ready = True

        # 1. Channels left over from before a restart: delete the empty ones, forget the ones that are gone
        for row in await self.bot.db.get_all_personal_channels():
            guild = self.bot.get_guild(row.guild_id)
            if guild is None or guild.unavailable:
                continue  # not in that server any more, or Discord is having a moment: leave the row be
            channel = guild.get_channel(row.channel_id)
            if not isinstance(channel, discord.VoiceChannel):
                await self.bot.db.remove_personal_channel(row.channel_id)
            elif (guild.id, row.owner_id) not in self.busy:
                await self.delete_if_empty(channel)

        # 2. Check each server's setup, and give anyone already waiting in the lobby their channel
        for guild_id, config in self.configs.items():
            guild = self.bot.get_guild(guild_id)
            if guild is None:
                logging.warning("Personal voice channels: set up for server %s, but I'm not in it any more.", guild_id)
                continue
            for problem in setup_problems(guild, config):
                self.warn_once(guild, problem)
            await self.serve_the_lobby(guild, config)

    async def serve_the_lobby(self, guild: discord.Guild, config: PersonalVcConfig) -> None:
        """Anyone sitting in the lobby (from before a restart, or before setup) gets their channel now."""
        hub = guild.get_channel(config.hub_channel_id)
        if isinstance(hub, discord.VoiceChannel):
            for member in humans_in(hub):
                await self.handle_lobby(member, config)

    # ---- people moving between voice channels

    @commands.Cog.listener()
    async def on_voice_state_update(
        self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState
    ):
        """Runs whenever someone joins, leaves or moves between voice channels (and on mute/deafen/stream too)."""
        if before.channel == after.channel:
            return  # muted, deafened, started streaming...: they didn't go anywhere
        if isinstance(before.channel, discord.VoiceChannel):
            await self.delete_if_empty(before.channel)
        config = self.configs.get(member.guild.id)
        if config and after.channel and after.channel.id == config.hub_channel_id and not member.bot:
            await self.handle_lobby(member, config)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        # Someone deleted a personal channel by hand: forget it, so its owner can get a new one
        await self.bot.db.remove_personal_channel(channel.id)

    async def delete_if_empty(self, channel: discord.VoiceChannel) -> None:
        """Deletes a personal channel (and forgets it) once nobody's left. Does nothing to any other channel."""
        if await self.bot.db.get_personal_channel_owner(channel.id) is None:
            return  # not a personal channel
        if not rules.should_delete(len(humans_in(channel))):
            return
        try:
            await channel.delete(reason="Personal voice channel: the last person left")
        except discord.NotFound:
            pass  # already gone
        except discord.HTTPException as error:
            # Keep the row: the startup tidy-up tries again next time
            self.warn_once(channel.guild, f"I couldn't delete an empty personal channel ({error}).")
            return
        await self.bot.db.remove_personal_channel(channel.id)

    async def owned_channel(self, guild: discord.Guild, owner_id: int) -> Optional[discord.VoiceChannel]:
        """Someone's personal channel in this server, if they have one. Forgets channels that have disappeared."""
        channel_id = await self.bot.db.get_owned_personal_channel(guild.id, owner_id)
        if channel_id is None:
            return None
        channel = guild.get_channel(channel_id)
        if not isinstance(channel, discord.VoiceChannel):
            await self.bot.db.remove_personal_channel(channel_id)
            return None
        return channel

    def in_lobby(self, member: discord.Member) -> bool:
        """Is this member still sitting in the lobby (and are personal channels still on)?
        member.voice is always up to date: discord.py looks it up fresh each time."""
        config = self.configs.get(member.guild.id)
        return bool(
            config and member.voice and member.voice.channel and member.voice.channel.id == config.hub_channel_id
        )

    async def handle_lobby(self, member: discord.Member, config: PersonalVcConfig) -> None:
        """Someone joined the lobby: move them into their channel, making it first if they don't have one."""
        key = (member.guild.id, member.id)
        if key in self.busy:
            return  # already on it (e.g. waiting out their cooldown); that run checks the lobby again at the end
        self.busy.add(key)
        try:
            await self._handle_lobby(member, config)
        finally:
            self.busy.discard(key)

    async def _handle_lobby(self, member: discord.Member, config: PersonalVcConfig) -> None:
        guild = member.guild
        problems = setup_problems(guild, config)
        if problems:
            # Don't even try: Discord would refuse, and we'd ask again on every join
            for problem in problems:
                self.warn_once(guild, problem)
            return

        # One channel per person: already got one (they stepped out, others stayed)? Back in you go.
        existing = await self.owned_channel(guild, member.id)
        if existing is not None:
            await self.move(member, existing)
            return

        # The cooldown: if they just had a channel, wait out the rest, then only go on if they're still waiting
        wait = rules.cooldown_left(self.last_created.get((guild.id, member.id)), time.monotonic())
        if wait:
            await asyncio.sleep(wait)
            if not self.in_lobby(member):
                return
            config = self.configs[guild.id]  # in_lobby checked it's still on; a VIP may have re-run setup meanwhile
        await self.create_for(member, guild.get_channel(config.hub_channel_id).category, config)

    async def create_for(self, member: discord.Member, category: discord.CategoryChannel, config: PersonalVcConfig):
        """Makes someone's channel with their saved mode and guests, moves them in and says hello."""
        guild = member.guild
        mode = rules.mode_from_db(await self.bot.db.get_personal_vc_mode(guild.id, member.id))
        guests = await self.bot.db.get_personal_vc_guests(guild.id, member.id)
        try:
            # Made inside the category with no permissions of its own, so it starts synced: a copy of the
            # category's permissions, exactly like a channel a mod makes there by hand
            channel = await category.create_voice_channel(
                rules.channel_name(member.display_name), reason=f"Personal voice channel for {member} ({member.id})"
            )
        except discord.HTTPException as error:
            self.warn_once(guild, f"I couldn't make a personal channel ({error}).")
            return
        self.last_created[(guild.id, member.id)] = time.monotonic()
        await self.bot.db.add_personal_channel(channel.id, guild.id, member.id)
        logging.info(
            "Personal voice channels: made '%s' for %s (%s) in '%s'", channel.name, member, member.id, guild.name
        )

        if mode is not Mode.OPEN:
            await self.apply_mode(channel, config, member.id, mode, guests)
        # They might have left (or wandered off to another channel) while we were busy: don't drag them back
        if not self.in_lobby(member) or not await self.move(member, channel):
            await self.delete_if_empty(channel)
            return

        welcome = [lines.WELCOME.format(owner=member.mention)]
        back = lines.welcome_back(member.display_name, mode, len(guests))
        if back:
            welcome.append(back)
        welcome.append(lines.PANEL)
        try:
            # Voice channels have their own text chat, and the same panel goes there. A new ControlPanel (same
            # class, same custom_ids) because discord.py keeps track of each sent view per message.
            await channel.send("\n".join(welcome), view=self.new_panel())
        except discord.HTTPException as error:
            self.warn_once(guild, f"I couldn't post the welcome in a personal channel's chat ({error}).")

    async def move(self, member: discord.Member, channel: discord.VoiceChannel) -> bool:
        try:
            await member.move_to(channel, reason="Personal voice channel")
        except discord.HTTPException as error:
            # Most often they hung up a moment before the move (Discord can't move someone who isn't connected)
            logging.info(
                "Personal voice channels: couldn't move %s (%s) to '%s': %s", member, member.id, channel, error
            )
            return False
        return True

    # ---- permissions

    async def apply_mode(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        channel: discord.VoiceChannel,
        config: PersonalVcConfig,
        owner_id: int,
        mode: Mode,
        guests: list[int],
    ) -> bool:
        """Sets the channel's permissions for this mode. Returns True if Discord took it."""
        guild = channel.guild
        # The owner, the staff role and the bot itself are always let in. The bot needs its own allow: Discord
        # only lets a bot allow permissions it has itself, and it has to keep seeing the channel to manage it.
        insiders = [owner_id, guild.me.id] + ([config.staff_role_id] if config.staff_role_id else [])
        present = [person.id for person in channel.members]  # already inside: they stay (not saved as guests)
        let_in = rules.let_in_ids(mode, insiders, guests, present)
        try:
            await channel.edit(overwrites=build_overwrites(channel, mode, let_in), reason=f"Personal channel: {mode}")
        except discord.HTTPException as error:
            self.warn_once(guild, f"I couldn't change a personal channel's permissions ({error}).")
            return False
        return True

    async def change_members(self, channel: discord.VoiceChannel, add: list[int], remove: list[int]) -> bool:
        """Adds a Let-in allow for some people and takes others' overwrites off, without touching the rest."""
        guild = channel.guild
        overwrites = {
            target: copy_overwrite(ow) for target, ow in channel.overwrites.items() if target.id not in remove
        }
        for member_id in add:
            member = guild.get_member(member_id)
            if member is not None:
                overwrite = overwrites.get(member, discord.PermissionOverwrite())
                overwrite.update(**rules.LET_IN)
                overwrites[member] = overwrite
        try:
            await channel.edit(overwrites=overwrites, reason="Personal channel: guest list changed")
        except discord.HTTPException as error:
            self.warn_once(guild, f"I couldn't change a personal channel's permissions ({error}).")
            return False
        return True

    # ---- the panel's buttons (personal_vc/ui.py calls these)

    async def find_own_channel(self, interaction: discord.Interaction) -> Optional[discord.VoiceChannel]:
        """The channel whose chat the button was pressed in, if the presser owns it. Otherwise None, after
        telling them why (privately). The buttons only live in personal channels' own chats, so "this channel"
        is always the one the panel belongs to."""
        guild = interaction.guild
        config = self.configs.get(guild.id) if guild else None
        if config is None:
            await interaction.response.send_message(lines.SWITCHED_OFF, ephemeral=True)
            return None
        hub = f"<#{config.hub_channel_id}>"
        channel = interaction.channel
        owner_id = None
        if isinstance(channel, discord.VoiceChannel):
            owner_id = await self.bot.db.get_personal_channel_owner(channel.id)
        if owner_id is None:
            # An old panel somewhere else, or a channel that's already been tidied away
            await interaction.response.send_message(lines.NOT_HERE.format(hub=hub), ephemeral=True)
            return None
        if owner_id != interaction.user.id:
            await interaction.response.send_message(
                lines.NOT_YOURS.format(owner=f"<@{owner_id}>", hub=hub), ephemeral=True
            )
            return None
        return channel

    async def on_mode(self, interaction: discord.Interaction, mode: Mode) -> None:
        channel = await self.find_own_channel(interaction)
        if channel is None:
            return
        # Changing permissions can take a moment, and Discord wants an answer within 3 seconds: defer says
        # "working on it" (privately), and the real answer follows
        await interaction.response.defer(ephemeral=True, thinking=True)
        guild, owner = interaction.guild, interaction.user
        await self.bot.db.set_personal_vc_mode(guild.id, owner.id, mode)
        guests = await self.bot.db.get_personal_vc_guests(guild.id, owner.id)
        worked = await self.apply_mode(channel, self.configs[guild.id], owner.id, mode, guests)
        await interaction.followup.send(lines.MODE_SET[mode] if worked else lines.MODE_FAILED, ephemeral=True)

    async def open_picker(self, interaction: discord.Interaction, content: str, picker: Picker) -> None:
        picker.opened_by = interaction
        await interaction.response.send_message(content, view=picker, ephemeral=True)

    async def on_let_in(self, interaction: discord.Interaction) -> None:
        if await self.find_own_channel(interaction) is not None:
            await self.open_picker(interaction, lines.LET_IN_PROMPT, LetInPicker(self.let_in_picked))

    async def let_in_picked(self, interaction: discord.Interaction, user_ids: list[int]) -> None:
        await interaction.response.defer()  # "working on it", then edit the private message with the answer
        guild, owner = interaction.guild, interaction.user
        guests = await self.bot.db.get_personal_vc_guests(guild.id, owner.id)
        new = [user_id for user_id in dict.fromkeys(user_ids) if user_id != owner.id and user_id not in guests]
        if not new:
            await interaction.edit_original_response(content=lines.LET_IN_NOBODY, view=None)
            return
        if len(guests) + len(new) > MAX_GUESTS:
            content = lines.LIST_FULL.format(limit=MAX_GUESTS, total=len(guests) + len(new))
            await interaction.edit_original_response(content=content, view=None)
            return
        await self.bot.db.add_personal_vc_guests(guild.id, owner.id, new)
        channel = await self.owned_channel(guild, owner.id)
        mode = rules.mode_from_db(await self.bot.db.get_personal_vc_mode(guild.id, owner.id))
        # An open channel lets everyone in already; the saved list takes effect the moment they lock or hide it
        worked = True
        if channel is not None and mode is not Mode.OPEN:
            worked = await self.change_members(channel, add=new, remove=[])
        content = lines.LET_IN_DONE.format(names=lines.names_list([f"<@{user_id}>" for user_id in new]))
        await interaction.edit_original_response(content=content if worked else lines.MODE_FAILED, view=None)

    async def on_remove(self, interaction: discord.Interaction) -> None:
        if await self.find_own_channel(interaction) is None:
            return
        guests = await self.bot.db.get_personal_vc_guests(interaction.guild.id, interaction.user.id)
        if not guests:
            await interaction.response.send_message(lines.NO_GUESTS, ephemeral=True)
            return
        names = []
        for user_id in guests:
            member = interaction.guild.get_member(user_id)
            names.append((user_id, member.display_name if member else lines.UNKNOWN_GUEST.format(user_id=user_id)))
        await self.open_picker(interaction, lines.REMOVE_PROMPT, RemovePicker(names, self.remove_picked))

    async def remove_picked(self, interaction: discord.Interaction, user_ids: list[int]) -> None:
        await interaction.response.defer()
        guild, owner = interaction.guild, interaction.user
        await self.bot.db.remove_personal_vc_guests(guild.id, owner.id, user_ids)
        channel = await self.owned_channel(guild, owner.id)
        worked = True
        if channel is not None and any(target.id in user_ids for target in channel.overwrites):
            # Takes their channel permission off; nobody gets disconnected
            worked = await self.change_members(channel, add=[], remove=user_ids)
        content = lines.REMOVE_DONE.format(names=lines.names_list([f"<@{user_id}>" for user_id in user_ids]))
        await interaction.edit_original_response(content=content if worked else lines.MODE_FAILED, view=None)

    # ---- /personalvc commands

    async def describe(self, guild: discord.Guild, config: PersonalVcConfig) -> discord.Embed:
        """The setup as an embed, with anything that would stop it working."""
        open_now = sum(row.guild_id == guild.id for row in await self.bot.db.get_all_personal_channels())
        staff = f"<@&{config.staff_role_id}> (sees and joins everything)" if config.staff_role_id else "nobody extra"
        description = "\n".join(
            [
                f"**Lobby** · <#{config.hub_channel_id}>",
                f"**Staff** · {staff}",
                f"**Channels rolling right now** · {open_now}",
            ]
        )
        embed = discord.Embed(title="🎞️ Personal voice channels", description=description, colour=EMBED_COLOUR)
        problems = setup_problems(guild, config)
        if problems:
            embed.add_field(name="⚠️ Something's stopping it", value="\n".join(problems), inline=False)
        embed.set_footer(text="🔓 Open · 🔒 Locked · 👻 Hidden. Everyone's mode and guest list are remembered.")
        return embed

    @app_commands.command(name="setup", description="VIP: pick the lobby and the staff role.")
    @app_commands.describe(
        hub="The lobby: the voice channel people join to get their own. Must be in a category.",
        staff="Moderators: they can see and join every personal channel, even hidden ones (leave out for none)",
    )
    @is_vip()
    async def setup(
        self,
        interaction: discord.Interaction,
        hub: discord.VoiceChannel,
        staff: Optional[discord.Role] = None,
    ) -> None:
        guild = interaction.guild
        if hub.category is None:
            await interaction.response.send_message(lines.SETUP_NEEDS_CATEGORY, ephemeral=True)
            return
        if staff is not None and staff.is_default():
            await interaction.response.send_message(lines.SETUP_BAD_STAFF, ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)  # serving the lobby can take a moment

        config = PersonalVcConfig(guild.id, hub.id, staff.id if staff else None)
        await self.bot.db.set_personal_vc_config(config)
        self.configs[guild.id] = config
        self.warned = {warning for warning in self.warned if warning[0] != guild.id}  # new setup, warn again
        logging.info(
            "Personal voice channels set up in '%s' by %s (%s)", guild.name, interaction.user, interaction.user.id
        )
        await interaction.followup.send(lines.SETUP_DONE, embed=await self.describe(guild, config), ephemeral=True)
        await self.serve_the_lobby(guild, config)

    @app_commands.command(name="show", description="Shows where personal voice channels live, and if anything's wrong.")
    async def show(self, interaction: discord.Interaction) -> None:
        config = self.configs.get(interaction.guild.id)
        if config is None:
            await interaction.response.send_message(lines.NOT_SET_UP, ephemeral=True)
            return
        embed = await self.describe(interaction.guild, config)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="off", description="VIP: no new personal channels. Open ones stay until they empty.")
    @is_vip()
    async def off(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        self.configs.pop(guild.id, None)
        await self.bot.db.clear_personal_vc_config(guild.id)
        logging.info("Personal voice channels switched off in '%s' by %s", guild.name, interaction.user.id)
        await interaction.response.send_message(lines.SWITCHED_OFF_DONE, ephemeral=True)


async def setup(bot):
    await bot.add_cog(PersonalVC(bot))
