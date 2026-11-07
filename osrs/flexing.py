"""The flexing webhooks: find them, create them, replace them, and build the "what to paste into Dink" kit.

A Discord webhook is a URL that lets anything post into one channel, without being a bot. Dink (a RuneLite
plugin) posts drops to it. Whoever has the URL can post, so it's treated like a password: the bot hands it out
privately and can swap it for a new one if it leaks.

The bot creates the webhooks itself (that needs the Manage Webhooks permission) and doesn't store their URLs
anywhere: when someone needs one, it asks Discord. Discord is the only place the secret lives.
"""

import logging
import os
from typing import Optional

import discord

from osrs import lines

# The name each webhook posts under (what everyone sees above the drop). The deaths one keeps the name the old
# setup used in #everyone-point-and-laugh, after swannobi's death message "Sit respectfully %USERNAME%".
WEBHOOK_NAME = "Ugandan Flexing"
DEATHS_WEBHOOK_NAME = "sit, respectfully"


class FlexingNotSetUp(Exception):
    """OSRS_FLEXING_CHANNEL_ID isn't set, or points at a channel the bot can't see."""


def _channel_from_env(bot: discord.Client, variable: str) -> Optional[discord.TextChannel]:
    """The text channel whose ID is in an environment variable, or None if it's not set or not found."""
    channel_id = os.getenv(variable, "").strip()
    if not channel_id.isdigit():
        return None
    channel = bot.get_channel(int(channel_id))  # from discord.py's cache: no API call
    return channel if isinstance(channel, discord.TextChannel) else None


def log_settings(bot: discord.Client) -> None:
    """Says in the log whether flexing is on. Missing or wrong settings only switch flexing off: the bot must
    always start, because the production host rolls back a release that doesn't. Run once the bot is
    connected, since before that discord.py doesn't know any channels yet."""
    for variable, required in (("OSRS_FLEXING_CHANNEL_ID", True), ("OSRS_DEATHS_CHANNEL_ID", False)):
        value = os.getenv(variable, "").strip()
        if not value:
            if required:
                logging.warning("%s not set: OSRS drop flexing is off (/osrs flexing says so).", variable)
        elif _channel_from_env(bot, variable) is None:
            logging.warning("%s=%s isn't a text channel the bot can see: that part of flexing is off.", variable, value)


def flexing_channels(bot: discord.Client) -> tuple[discord.TextChannel, Optional[discord.TextChannel]]:
    """(main flexing channel, deaths channel or None). Deaths go to their own channel only if one is set."""
    main = _channel_from_env(bot, "OSRS_FLEXING_CHANNEL_ID")
    if main is None:
        raise FlexingNotSetUp()
    return main, _channel_from_env(bot, "OSRS_DEATHS_CHANNEL_ID")


async def _our_webhooks(channel: discord.TextChannel, bot_user: discord.ClientUser) -> list[discord.Webhook]:
    """The webhooks in this channel that this bot made. We never touch ones a person made by hand."""
    return [
        hook
        for hook in await channel.webhooks()  # raises discord.Forbidden without Manage Webhooks
        if hook.type == discord.WebhookType.incoming and hook.user and hook.user.id == bot_user.id and hook.token
    ]


async def get_or_create_webhook(
    channel: discord.TextChannel, bot_user: discord.ClientUser, name: str = WEBHOOK_NAME
) -> discord.Webhook:
    """The bot's webhook in this channel, created the first time it's needed."""
    existing = await _our_webhooks(channel, bot_user)
    if existing:
        return existing[0]
    return await channel.create_webhook(name=name, reason="VideoJoker: OSRS drop flexing")


async def replace_webhook(
    channel: discord.TextChannel, bot_user: discord.ClientUser, name: str = WEBHOOK_NAME
) -> discord.Webhook:
    """Deletes the bot's webhook(s) here and makes a new one with the same name and picture.

    Deleting is what stops a leaked URL: from that moment it posts nothing, wherever it was pasted.
    """
    old_hooks = await _our_webhooks(channel, bot_user)
    avatar = None
    if old_hooks:
        name = old_hooks[0].name or name  # keep a name someone changed in Discord
        if old_hooks[0].avatar:  # someone gave it a picture in Discord's settings: keep it
            avatar = await old_hooks[0].avatar.read()
    for hook in old_hooks:
        await hook.delete(reason="VideoJoker: /osrs rotate-webhook")
    return await channel.create_webhook(name=name, avatar=avatar, reason="VideoJoker: /osrs rotate-webhook")


def build_kit(main_url: str, deaths_url: Optional[str]) -> str:
    """The step-by-step "what to paste into Dink" message. Each URL sits in its own code block, which
    makes it easy to copy on a phone (long-press → copy).

    deaths_url is the deaths channel's webhook if they want their deaths shown there, otherwise None.
    """
    parts = [lines.FLEX_KIT_TITLE, lines.FLEX_KIT_PRIMARY.format(url=main_url)]
    if deaths_url:
        parts.append(lines.FLEX_KIT_DEATHS.format(url=deaths_url))
    else:
        parts.append(lines.FLEX_KIT_NO_DEATHS)
    parts.append(lines.FLEX_KIT_SETTINGS.format(url=lines.DINK_SETTINGS_URL))
    parts.append(lines.FLEX_KIT_SECRET)
    return "\n".join(parts)


async def make_kit(bot: discord.Client, deaths: bool) -> str:
    """Builds someone's flexing kit, creating the webhook(s) the first time they're needed.

    deaths: whether they want their deaths posted in the deaths channel (ignored if there isn't one).
    Raises FlexingNotSetUp, or discord.Forbidden if the bot lacks Manage Webhooks.
    """
    main, deaths_channel = flexing_channels(bot)
    main_hook = await get_or_create_webhook(main, bot.user)
    deaths_hook = None
    if deaths and deaths_channel:
        deaths_hook = await get_or_create_webhook(deaths_channel, bot.user, DEATHS_WEBHOOK_NAME)
    return build_kit(main_hook.url, deaths_hook.url if deaths_hook else None)
