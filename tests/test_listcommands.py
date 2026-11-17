"""Tests for /listcommands and /listadmincommands (bot.py), on the bot's real commands: VIP-only commands go on
the VIP list and nowhere else, subcommands get their own lines, and the embeds fit inside Discord's limits."""

import inspect
import re
from types import SimpleNamespace

import discord
from discord import app_commands
from discord.ext import commands

from cogs.permissions import is_vip_command
from tests.real_commands import build_bot, commands_by_name


async def run(bot, name: str) -> dict:
    """Runs a root command's code directly (its checks, like is_vip, are skipped) and returns what it sent."""
    sent = {}

    async def send_message(content=None, **kwargs):  # stands in for Discord: keeps what would have been sent
        sent.update(content=content, **kwargs)

    interaction = SimpleNamespace(client=bot, response=SimpleNamespace(send_message=send_message))
    await bot.tree.get_command(name).callback(interaction)
    return sent


def listed_names(sent: dict) -> list[str]:
    """The command names on a list: each line looks like **/ladder show** - Shows the rank ladder..."""
    text = "\n".join(field.value for embed in sent["embeds"] for field in embed.fields)
    return re.findall(r"\*\*/(.+?)\*\*", text)


# ---- Which commands are VIP-only


async def test_vip_only_commands_are_recognised():
    real = commands_by_name(build_bot())
    for name in ["setup ladder set", "setup ladder off", "setup ladder tidy", "setup voice set", "setup voice off"]:
        assert is_vip_command(real[name]), name
    for name in [
        "setup people ban",
        "setup people vip",
        "setup people reset",
        "setup osrs-webhook",
        "listadmincommands",
    ]:
        assert is_vip_command(real[name]), name


async def test_everyday_commands_are_not_vip_only():
    real = commands_by_name(build_bot())
    for name in ["ladder show", "osrs register", "help", "listcommands", "play"]:
        assert not is_vip_command(real[name]), name


async def test_every_setup_command_is_vip_only_and_hidden_from_members():
    bot = build_bot()
    setup = bot.tree.get_command("setup")
    # Hidden from the / menu for anyone who can't Manage Server (Discord's own setting, on the whole group)
    assert setup.default_permissions == discord.Permissions(manage_guild=True)
    for command in setup.walk_commands():
        if isinstance(command, app_commands.Command):
            assert is_vip_command(command), command.qualified_name


def test_a_group_on_its_own_is_not_vip_only():
    assert not is_vip_command(SimpleNamespace())  # no checks at all, like a group: no crash, just False


# ---- The two lists


async def test_the_two_lists_split_every_command_between_them():
    bot = build_bot()
    everyone = listed_names(await run(bot, "listcommands"))
    vips = listed_names(await run(bot, "listadmincommands"))

    assert not set(everyone) & set(vips)  # nothing on both
    assert sorted(everyone + vips) == sorted(commands_by_name(bot))  # and nothing missing
    assert "ladder show" in everyone and "setup ladder set" in vips
    assert "ladder" not in everyone  # the group itself isn't a line: its subcommands are


async def test_listcommands_is_public_and_listadmincommands_only_for_you():
    bot = build_bot()
    assert (await run(bot, "listcommands"))["ephemeral"] is False
    assert (await run(bot, "listadmincommands"))["ephemeral"] is True


async def test_the_lists_fit_in_discords_limits():
    bot = build_bot()
    for name in ["listcommands", "listadmincommands"]:
        embeds = (await run(bot, name))["embeds"]
        assert 1 <= len(embeds) <= 10  # one message carries at most 10 embeds
        for embed in embeds:
            assert len(embed) <= 6000 and len(embed.fields) <= 25
            assert all(len(field.value) <= 1024 for field in embed.fields)


# ---- "@VideoJoker ping" (a text command, so it's in nobody's / menu)


def ping_context(*, admin: bool, in_server: bool = True) -> SimpleNamespace:
    """Just enough of a commands.Context for ping's checks and its reply."""
    sent = []

    async def send(content):
        sent.append(content)

    permissions = discord.Permissions(administrator=admin)
    return SimpleNamespace(guild=object() if in_server else None, permissions=permissions, send=send, sent=sent)


async def passes_checks(command, ctx) -> bool:
    try:
        for check in command.checks:
            result = check(ctx)
            if inspect.isawaitable(result):
                result = await result
        return True
    except commands.CheckFailure:
        return False


def test_ping_is_not_a_slash_command():
    assert "ping" not in commands_by_name(build_bot())


async def test_ping_answers_admins_with_the_version():
    ping = build_bot().get_command("ping")
    ctx = ping_context(admin=True)
    assert await passes_checks(ping, ctx)
    await ping.callback(ctx)
    assert ctx.sent == ["pong · dev"]


async def test_ping_ignores_everyone_else():
    ping = build_bot().get_command("ping")
    assert not await passes_checks(ping, ping_context(admin=False))
    assert not await passes_checks(ping, ping_context(admin=True, in_server=False))  # DMs have no admins


async def test_every_setup_command_hands_its_work_to_a_method_that_exists():
    """/setup's commands each call one method on a feature's cog (cogs/server_setup.py). A renamed method there
    would only fail when a VIP runs the command, so check every call against the real cogs here."""
    import ast  # pylint: disable=import-outside-toplevel

    from cogs import server_setup  # pylint: disable=import-outside-toplevel
    from tests.real_commands import cog_classes  # pylint: disable=import-outside-toplevel

    cogs_by_name = {cog_class.__cog_name__: cog_class for cog_class in cog_classes()}
    tree = ast.parse(inspect.getsource(server_setup))
    calls = []
    for function in ast.walk(tree):
        if not isinstance(function, ast.AsyncFunctionDef):
            continue
        cog_name = next(
            (
                node.args[1].value
                for node in ast.walk(function)
                if isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "feature"
            ),
            None,
        )
        if cog_name is None:  # /setup show: checked below, through SHOW_ORDER
            continue
        for node in ast.walk(function):
            if isinstance(node, ast.Call) and getattr(getattr(node.func, "value", None), "id", "") == "cog":
                calls.append((cog_name, node.func.attr, len(node.args)))
    assert len(calls) >= 16
    for cog_name, method, arg_count in calls:
        target = getattr(cogs_by_name[cog_name], method)
        inspect.signature(target).bind(object(), *range(arg_count))  # raises if the arguments don't fit
    for _title, cog_name in server_setup.SHOW_ORDER:
        assert inspect.iscoroutinefunction(cogs_by_name[cog_name].setup_summary), cog_name
