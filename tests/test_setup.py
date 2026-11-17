"""Tests for who can run what, on the bot's real commands: VIP-only commands are recognised, the hidden /setup group
is hidden and VIP-only all the way down, and every /setup command hands its work to a method that exists.
(This file held the /listcommands tests until /help took over its job on 2026-11-16.)"""

import inspect
from types import SimpleNamespace

import discord
from discord import app_commands

from cogs.permissions import is_vip_command
from tests.real_commands import build_bot, commands_by_name


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
        "setup show",
    ]:
        assert is_vip_command(real[name]), name


async def test_everyday_commands_are_not_vip_only():
    real = commands_by_name(build_bot())
    for name in ["profile", "osrs register", "help", "raffle start", "play"]:
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
