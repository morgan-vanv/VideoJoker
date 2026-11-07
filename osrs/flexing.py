"""The flexing webhooks: find them, create them, replace them, and build the "what to paste into Dink" kit.

A Discord webhook is a URL that lets anything post into one channel, without being a bot. Dink (a RuneLite
plugin) posts drops to it. Whoever has the URL can post, so it's treated like a password: the bot hands it out
privately and can swap it for a new one if it leaks.

The bot creates the webhooks itself (that needs the Manage Webhooks permission) and doesn't store their URLs
anywhere: when someone needs one, it asks Discord. Discord is the only place the secret lives.
"""

import os
from typing import Optional

import discord

from osrs import lines

WEBHOOK_NAME = "Ugandan Flexing"


class FlexingNotSetUp(Exception):
    """OSRS_FLEXING_CHANNEL_ID isn't set, or points at a channel the bot can't see."""


def _channel_from_env(bot: discord.Client, variable: str) -> Optional[discord.TextChannel]:
    """The text channel whose ID is in an environment variable, or None if it's not set or not found."""
    channel_id = os.getenv(variable, "").strip()
    if not channel_id.isdigit():
        return None
    channel = bot.get_channel(int(channel_id))  # from discord.py's cache: no API call
    return channel if isinstance(channel, discord.TextChannel) else None


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


async def get_or_create_webhook(channel: discord.TextChannel, bot_user: discord.ClientUser) -> discord.Webhook:
    """The bot's webhook in this channel, created the first time it's needed."""
    existing = await _our_webhooks(channel, bot_user)
    if existing:
        return existing[0]
    return await channel.create_webhook(name=WEBHOOK_NAME, reason="VideoJoker: OSRS drop flexing")


async def replace_webhook(channel: discord.TextChannel, bot_user: discord.ClientUser) -> discord.Webhook:
    """Deletes the bot's webhook(s) here and makes a new one with the same name and picture.

    Deleting is what stops a leaked URL: from that moment it posts nothing, wherever it was pasted.
    """
    old_hooks = await _our_webhooks(channel, bot_user)
    name, avatar = WEBHOOK_NAME, None
    if old_hooks:
        name = old_hooks[0].name or WEBHOOK_NAME
        if old_hooks[0].avatar:  # someone gave it a picture in Discord's settings: keep it
            avatar = await old_hooks[0].avatar.read()
    for hook in old_hooks:
        await hook.delete(reason="VideoJoker: /osrs rotate-webhook")
    return await channel.create_webhook(name=name, avatar=avatar, reason="VideoJoker: /osrs rotate-webhook")


def build_kit(main_url: str, deaths_url: Optional[str]) -> str:
    """The step-by-step "what to paste into Dink" message. Each URL sits in its own code block, which
    makes it easy to copy on a phone (long-press → copy)."""
    parts = [lines.FLEX_KIT_TITLE, lines.FLEX_KIT_PRIMARY.format(url=main_url)]
    if deaths_url:
        parts.append(lines.FLEX_KIT_DEATHS.format(url=deaths_url))
    else:
        parts.append(lines.FLEX_KIT_NO_OVERRIDES)
    parts.append(lines.FLEX_KIT_SETTINGS.format(url=lines.DINK_SETTINGS_URL))
    parts.append(lines.FLEX_KIT_SECRET)
    return "\n".join(parts)


async def make_kit(bot: discord.Client) -> str:
    """Builds someone's flexing kit, creating the webhook(s) if this is the first time.

    Raises FlexingNotSetUp, or discord.Forbidden if the bot lacks Manage Webhooks.
    """
    main, deaths = flexing_channels(bot)
    main_hook = await get_or_create_webhook(main, bot.user)
    deaths_hook = await get_or_create_webhook(deaths, bot.user) if deaths else None
    return build_kit(main_hook.url, deaths_hook.url if deaths_hook else None)
