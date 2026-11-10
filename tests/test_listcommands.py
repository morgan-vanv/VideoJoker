"""Tests for /listcommands and /listadmincommands (bot.py), on the bot's real commands: VIP-only commands go on
the VIP list and nowhere else, subcommands get their own lines, and the embeds fit inside Discord's limits."""

import re
from types import SimpleNamespace

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
    for name in ["ladder setup", "ladder off", "ladder tidy", "personalvc setup", "personalvc off"]:
        assert is_vip_command(real[name]), name
    for name in ["grantbanuser", "grantvipuser", "resetpermissions", "osrs rotate-webhook", "listadmincommands"]:
        assert is_vip_command(real[name]), name


async def test_everyday_commands_are_not_vip_only():
    real = commands_by_name(build_bot())
    for name in ["ladder show", "personalvc show", "osrs register", "help", "listcommands", "ping", "play"]:
        assert not is_vip_command(real[name]), name
    # Anyone (not banned) can look these up: they only read, so they're not VIP-only
    for name in ["checkpermissions", "listvipusers", "listbannedusers"]:
        assert not is_vip_command(real[name]), name


def test_a_group_on_its_own_is_not_vip_only():
    assert not is_vip_command(SimpleNamespace())  # no checks at all, like a group: no crash, just False


# ---- The two lists


async def test_the_two_lists_split_every_command_between_them():
    bot = build_bot()
    everyone = listed_names(await run(bot, "listcommands"))
    vips = listed_names(await run(bot, "listadmincommands"))

    assert not set(everyone) & set(vips)  # nothing on both
    assert sorted(everyone + vips) == sorted(commands_by_name(bot))  # and nothing missing
    assert "ladder show" in everyone and "ladder setup" in vips
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


async def test_ping_is_hidden_from_everyone_but_admins():
    # Discord hides a command with default permissions from the / menu of anyone who lacks them
    ping = commands_by_name(build_bot())["ping"]
    assert ping.default_permissions is not None
    assert ping.default_permissions.administrator
