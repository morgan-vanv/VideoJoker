"""The /ladder commands and the listener that promotes people: LOWLY SERFS → SWORN SWORDS → LORDS.

The rules (what rank you've earned, never demoting, one rank at a time) live in ranks/ladder.py and are
tested there. This file is the Discord side: it reads a member's roles, asks the rules what to do, and does it.

Needs, on the server: the Manage Roles permission, and the bot's own role ABOVE the three ladder roles in
Server Settings → Roles (Discord only lets a bot hand out roles below its highest one). See SETUP_GUIDE.md.
"""

import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from cogs.permissions import is_vip
from ranks.ladder import (
    DEFAULT_MIN_XP,
    TIER_NAMES,
    RoleChange,
    Tier,
    plan_promotion,
    plan_tidy,
    problems_with,
    rank_progress,
    tier_name,
    xp_shortfall,
)
from ranks.notes import rank_up_note, unlocked_permissions
from ranks.ui import ConfirmTidy
from standing.lines import EARNING, YOU_ARE_HERE, you_are_here

EMBED_COLOUR = discord.Colour.dark_gold()
# The highest threshold /ladder setup accepts (a typo guard: nobody is posting a million messages)
MAX_XP = 1_000_000


def role_problems(guild: discord.Guild, tiers: list[Tier], for_log: bool = False) -> list[str]:
    """What stops the bot from handing out these roles in this server, in plain words (empty = all good).
    for_log=True names roles as text; otherwise they're mentions, which Discord shows as the role's pill."""
    me = guild.me
    problems = []
    if not me.guild_permissions.manage_roles:
        problems.append("I need the **Manage Roles** permission.")
    for tier in tiers:
        name = TIER_NAMES.get(tier.number, f"Tier {tier.number}")
        role = guild.get_role(tier.role_id)
        if role is None:
            problems.append(f"The {name} role is gone (deleted?). Run `/ladder setup` again.")
            continue
        label = f"'{role.name}'" if for_log else role.mention
        if role.is_default() or role.managed:
            problems.append(f"{label} can't be a rank (it's @everyone or belongs to an app).")
        elif role >= me.top_role:
            problems.append(f"My role must sit **above** {label} in Server Settings → Roles.")
    return problems


def ladder_of(bot: commands.Bot, guild: Optional[discord.Guild]) -> Optional[list[Tier]]:
    """This server's ladder, for other cogs (/rank, /balance), or None: no server (a DM), no ladder set up, or the
    Ranks cog isn't loaded. The ladder lives in the Ranks cog's memory, so this costs no database trip."""
    ranks = bot.get_cog("Ranks")
    if guild is None or ranks is None:
        return None
    return ranks.ladders.get(guild.id)


def permissions_of(role: discord.Role) -> set[str]:
    """The server-wide permissions a role switches on, as names ({"attach_files", "add_reactions", ...}).
    Looping over a Permissions object gives (name, True/False) pairs, one per permission."""
    return {name for name, value in role.permissions if value}


def rank_label(guild: discord.Guild, tier: Tier) -> str:
    """A rank as its role mention, which embeds show as the role's coloured pill (and never ping). If the role was
    deleted, the plain name instead, because a mention of a missing role shows as "@deleted-role"."""
    return f"<@&{tier.role_id}>" if guild.get_role(tier.role_id) else f"**{tier_name(tier)}**"


@app_commands.guild_only()
class Ranks(commands.GroupCog, group_name="ladder", group_description="The XP rank ladder: serfs, swords, lords."):
    """XP rank ladder: earns members LOWLY SERFS, SWORN SWORDS and LORDS as they chat"""

    def __init__(self, bot):
        logging.info("Ranks cog initialized.")
        self.bot = bot
        # Every server's ladder, kept in memory: it's read on every single message, so no DB trip each time
        self.ladders: dict[int, list[Tier]] = {}
        # Servers we've already warned about in the log, so a missing permission doesn't log every message
        self.warned: set[int] = set()
        self.checked_on_ready = False

    async def cog_load(self):
        for row in await self.bot.db.get_all_rank_tiers():
            self.ladders.setdefault(row.guild_id, []).append(Tier(row.tier, row.role_id, row.min_xp))
        if self.ladders:
            logging.info("Rank ladder: on in %d server(s).", len(self.ladders))
        else:
            # Hosting contract: a feature with nothing set up switches off and says so, the bot still starts
            logging.warning("Rank ladder: off (no server has run /ladder setup yet).")

    @commands.Cog.listener()
    async def on_ready(self):
        # on_ready runs again after every reconnect; checking once per start is enough
        if self.checked_on_ready:
            return
        self.checked_on_ready = True
        for guild_id, tiers in self.ladders.items():
            guild = self.bot.get_guild(guild_id)
            if guild is None:
                logging.warning("Rank ladder: set up for server %s, but I'm not in it any more.", guild_id)
                continue
            for problem in role_problems(guild, tiers, for_log=True):
                logging.warning("Rank ladder in '%s': %s", guild.name, problem)

    # ---- the promoting part

    @commands.Cog.listener()
    async def on_xp_gained(self, member: discord.Member | discord.User, xp: int):
        """Custom event, sent by cogs/utility.py right after it adds XP for a message (so we see the new total,
        whichever listener Discord happens to run first). Commands come in through on_slash_command_finished."""
        await self.promote(member, xp)

    async def promote(self, member: discord.Member | discord.User, xp: int) -> None:
        """Gives them the rank their XP has earned, if it's new, and leaves them a note about it."""
        # A Member (with roles and a server) for anything said in a server; a plain User in DMs, or if they left
        if not isinstance(member, discord.Member):
            return
        tiers = self.ladders.get(member.guild.id)
        if not tiers:
            return
        change = plan_promotion(tiers, xp, {role.id for role in member.roles})
        if change is not None:
            promoted = await self.apply(member, tiers, change, reason=f"Rank ladder: reached {xp} server XP")
            if promoted:
                # Here, not in apply(): /ladder tidy uses apply() too, and tidying isn't climbing
                await self.bot.db.save_rank_up_note(member.guild.id, member.id, change.tier.number)

    # ---- the rank-up note (ranks/notes.py has the wording)

    @commands.Cog.listener()
    async def on_slash_command_finished(self, interaction: discord.Interaction, xp: Optional[int]):
        """Custom event, sent by cogs/utility.py after every slash command a person finishes in a server. xp is
        their new XP total, or None if the command earned none (the once-a-minute cooldown).

        Two jobs, one after the other in this one handler: first the promotion (if this command's XP earned a rank,
        its note gets saved), then delivering whatever note is waiting. If they were two listeners, Discord would run
        them side by side and the delivery could look before the promotion had saved its note."""
        if xp is not None:
            await self.promote(interaction.user, xp)
        await self.deliver_note(interaction)

    async def deliver_note(self, interaction: discord.Interaction) -> None:
        """Shows their waiting rank-up note, if any, privately (ephemeral) under the command's own reply. Never in a
        channel or a DM: people who don't use commands are left alone (their new role is still there to see)."""
        # The note is a followup, and a followup needs the command to have replied first. No reply? Keep the note.
        if not interaction.response.is_done():
            return
        guild, user = interaction.guild, interaction.user
        note = await self.bot.db.take_rank_up_note(guild.id, user.id)
        if note is None:
            return  # the usual case: nothing waiting
        text = await self.note_text(guild, user, note.tier)
        if text is None:
            logging.info(
                "Rank ladder: dropped %s's rank-up note in '%s' (ladder off or rank gone)", user.id, guild.name
            )
            return
        try:
            await interaction.followup.send(text, ephemeral=True, allowed_mentions=discord.AllowedMentions.none())
        except discord.HTTPException as error:
            # Discord said no (say the command's reply is gone): put the note back, the next command tries again
            await self.bot.db.put_back_rank_up_note(guild.id, user.id, note)
            logging.warning("Rank ladder: couldn't show %s their rank-up note, kept it: %s", user.id, error)

    async def note_text(self, guild: discord.Guild, user: discord.abc.User, tier_number: int) -> Optional[str]:
        """The note for climbing to this tier, or None if there's nothing to say any more: the ladder is off, or the
        tier or its role is gone."""
        tiers = self.ladders.get(guild.id, [])
        tier = next((tier for tier in tiers if tier.number == tier_number), None)
        role = guild.get_role(tier.role_id) if tier else None
        if role is None:
            return None
        xp = await self.bot.db.get_xp_totals(user.id)
        # Worked out as if they wear just this role: the note is about this rank, and right after a promotion
        # Discord may not have told us about their new role yet
        progress = rank_progress(tiers, xp.total, {role.id})
        lower_roles = [guild.get_role(lower.role_id) for lower in tiers if lower.number < tier.number]
        unlocked = unlocked_permissions(
            permissions_of(role),
            permissions_of(guild.default_role),  # default_role is @everyone
            [permissions_of(lower) for lower in lower_roles if lower is not None],
        )
        return rank_up_note(progress, unlocked)

    async def apply(self, member: discord.Member, tiers: list[Tier], change: RoleChange, reason: str) -> bool:
        """Adds/removes the roles in `change`. Returns True if it worked."""
        guild = member.guild
        if role_problems(guild, tiers):
            # Don't even try: Discord would refuse, and we'd ask again on every message
            if guild.id not in self.warned:
                self.warned.add(guild.id)
                for problem in role_problems(guild, tiers, for_log=True):
                    logging.warning("Rank ladder in '%s' is stuck: %s", guild.name, problem)
            return False
        try:
            # Add first, remove second: if Discord fails half-way, the member ends up with one rank too many
            # (harmless, /ladder tidy fixes it), never with one too few.
            if change.add is not None:
                await member.add_roles(guild.get_role(change.add), reason=reason)
            if change.remove:
                await member.remove_roles(*(guild.get_role(role_id) for role_id in change.remove), reason=reason)
        except discord.HTTPException as error:
            logging.warning("Rank ladder: couldn't update %s (%s) in '%s': %s", member, member.id, guild.name, error)
            return False
        logging.info(
            "Rank ladder: %s (%s) is now %s in '%s'",
            member,
            member.id,
            TIER_NAMES.get(change.tier.number, change.tier.number),
            guild.name,
        )
        return True

    # ---- commands

    def describe(self, guild: discord.Guild, tiers: list[Tier]) -> discord.Embed:
        """The ladder as an embed, top rank first, with anything that would stop it working."""
        lines = [
            f"**{TIER_NAMES.get(tier.number, f'Tier {tier.number}')}** · <@&{tier.role_id}> · {tier.min_xp:,} XP"
            for tier in sorted(tiers, key=lambda tier: tier.number, reverse=True)
        ]
        embed = discord.Embed(title="🎞️ The rank ladder", description="\n".join(lines), colour=EMBED_COLOUR)
        problems = role_problems(guild, tiers)
        if problems:
            embed.add_field(name="⚠️ The projector is jammed", value="\n".join(problems), inline=False)
        # The earning line comes from standing/lines.py, so /rank, /balance and this footer always agree
        embed.set_footer(text=f"{EARNING} XP is for life. Ranks only go up, one rank at a time.")
        return embed

    @app_commands.command(name="setup", description="VIP: pick the three rank roles and their XP thresholds.")
    @app_commands.describe(
        serfs="The first rank, earned with a member's first message",
        swords="The middle rank",
        lords="The top rank",
        swords_xp=f"XP for the middle rank (default: what it is now, or {DEFAULT_MIN_XP[2]})",
        lords_xp=f"XP for the top rank (default: what it is now, or {DEFAULT_MIN_XP[3]})",
    )
    @is_vip()
    # pylint: disable=too-many-arguments, too-many-positional-arguments
    async def setup(
        self,
        interaction: discord.Interaction,
        serfs: discord.Role,
        swords: discord.Role,
        lords: discord.Role,
        swords_xp: Optional[app_commands.Range[int, 2, MAX_XP]] = None,
        lords_xp: Optional[app_commands.Range[int, 2, MAX_XP]] = None,
    ) -> None:
        guild = interaction.guild
        # Left out? Keep this server's current threshold, so changing one number doesn't reset the other
        current = {tier.number: tier.min_xp for tier in self.ladders.get(guild.id, [])}
        tiers = [
            Tier(1, serfs.id, DEFAULT_MIN_XP[1]),
            Tier(2, swords.id, swords_xp or current.get(2, DEFAULT_MIN_XP[2])),
            Tier(3, lords.id, lords_xp or current.get(3, DEFAULT_MIN_XP[3])),
        ]
        problems = problems_with(tiers)
        if any(role.is_default() or role.managed for role in (serfs, swords, lords)):
            problems.append("@everyone and app roles can't be ranks.")
        if problems:
            await interaction.response.send_message(
                "🎬 Cut! That ladder won't stand:\n" + "\n".join(f"- {problem}" for problem in problems),
                ephemeral=True,
            )
            return

        await self.bot.db.set_rank_tiers(guild.id, [(tier.number, tier.role_id, tier.min_xp) for tier in tiers])
        self.ladders[guild.id] = tiers
        self.warned.discard(guild.id)  # new setup, so warn again if something's still wrong
        logging.info("Rank ladder set up in '%s' by %s (%s)", guild.name, interaction.user, interaction.user.id)
        await interaction.response.send_message(
            "🎬 The ladder is up, comrade. From now on every message counts.",
            embed=self.describe(guild, tiers),
            ephemeral=True,
        )

    @app_commands.command(name="show", description="Shows the rank ladder: which roles, and how much XP each needs.")
    async def show(self, interaction: discord.Interaction) -> None:
        tiers = self.ladders.get(interaction.guild.id)
        if not tiers:
            await interaction.response.send_message(
                "🎞️ No ladder on this reel yet. A VIP can start one with `/ladder setup`.", ephemeral=True
            )
            return
        embed = self.describe(interaction.guild, tiers)
        # Where the person asking stands: their rank (the role they wear), their XP and how far the next rank is
        xp = await self.bot.db.get_xp_totals(interaction.user.id)
        progress = rank_progress(tiers, xp.total, {role.id for role in interaction.user.roles})
        embed.add_field(
            name=YOU_ARE_HERE,
            value=you_are_here(progress, lambda tier: rank_label(interaction.guild, tier)),
            inline=False,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="off", description="VIP: stops handing out ranks here. Nobody loses a role.")
    @is_vip()
    async def off(self, interaction: discord.Interaction) -> None:
        await self.bot.db.clear_rank_tiers(interaction.guild.id)
        self.ladders.pop(interaction.guild.id, None)
        logging.info("Rank ladder switched off in '%s' by %s", interaction.guild.name, interaction.user.id)
        await interaction.response.send_message(
            "📼 Ladder's off. Everyone keeps the rank they have; nobody climbs until `/ladder setup` again.",
            ephemeral=True,
        )

    async def plan_tidy_for(
        self, guild: discord.Guild, tiers: list[Tier]
    ) -> tuple[list[tuple[discord.Member, RoleChange]], list[tuple[discord.Member, int]]]:
        """What /ladder tidy would do: (role changes, XP top-ups as (member, minimum XP)).
        guild.members is the whole list thanks to the members intent (bot.py). Two jobs per ranked member:
        take off extra lower ranks, and top their XP up to the minimum for the rank they wear."""
        all_xp = await self.bot.db.get_all_total_xp()
        changes, top_ups = [], []
        for member in guild.members:
            if member.bot:
                continue
            role_ids = {role.id for role in member.roles}
            change = plan_tidy(tiers, role_ids)
            if change is not None:
                changes.append((member, change))
            xp = all_xp.get(member.id, 0)
            shortfall = xp_shortfall(tiers, role_ids, xp)
            if shortfall:
                top_ups.append((member, xp + shortfall))
        return changes, top_ups

    @app_commands.command(name="tidy", description="VIP: one rank each, and enough XP for the rank they wear.")
    @is_vip()
    async def tidy(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        tiers = self.ladders.get(guild.id)
        if not tiers:
            await interaction.response.send_message("🎞️ Set up the ladder first: `/ladder setup`.", ephemeral=True)
            return
        problems = role_problems(guild, tiers)
        if problems:
            await interaction.response.send_message(
                "🎬 Can't tidy yet:\n" + "\n".join(f"- {problem}" for problem in problems), ephemeral=True
            )
            return

        changes, top_ups = await self.plan_tidy_for(guild, tiers)
        if not changes and not top_ups:
            await interaction.response.send_message(
                "📼 Nothing to fix. One rank each, and everyone has the XP to back it up.", ephemeral=True
            )
            return

        # The preview: what would change, before anything happens
        removals: dict[int, int] = {}
        for _member, change in changes:
            for role_id in change.remove:
                removals[role_id] = removals.get(role_id, 0) + 1
        preview = ["📼 Rewinding the tape. Nobody goes down a rank."]
        if changes:
            preview.append(f"**{len(changes)}** member(s) wear more than one rank and would keep only their highest:")
            preview += [f"- <@&{role_id}> off **{count}** member(s)" for role_id, count in removals.items()]
        if top_ups:
            preview.append(
                f"**{len(top_ups)}** member(s) have less XP than their rank needs and would be topped up to its "
                "minimum (it shows as carried-over XP in `/rank`)."
            )

        async def run(button_click: discord.Interaction) -> None:
            for member, minimum in top_ups:
                await self.bot.db.top_up_xp(member.id, minimum)
            logging.info("Rank ladder: /ladder tidy topped up XP for %d member(s) in '%s'", len(top_ups), guild.name)
            done = 0
            for member, change in changes:
                if await self.apply(member, tiers, change, reason=f"/ladder tidy by {interaction.user}"):
                    done += 1
            result = f"🎬 That's a wrap: **{done}** member(s) down to one rank, **{len(top_ups)}** XP top-up(s)."
            if done < len(changes):
                result += f" {len(changes) - done} role change(s) didn't take (see the bot log)."
            await button_click.edit_original_response(content=result)

        await interaction.response.send_message("\n".join(preview), view=ConfirmTidy(run), ephemeral=True)


async def setup(bot):
    await bot.add_cog(Ranks(bot))
