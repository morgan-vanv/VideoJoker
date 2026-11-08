"""The private note someone gets when they climb the ladder: their new rank, how far the next one is, and what the
new rank lets them do. Plain functions with no Discord in them (tested in tests/test_ranks.py); cogs/ranks.py
reads the roles and sends the note.

"What it lets them do" comes from the roles' real permissions, so the note stays right if Morgan changes a role
in Server Settings. Permissions are plain strings here, the names discord.py uses (e.g. "attach_files"): the cog
gets them with `{name for name, value in role.permissions if value}`.
"""

from typing import Iterable

from ranks.ladder import RankProgress, tier_name

# Discord's permission names in everyday words, in the order the note lists them. A permission missing from here
# still shows up, as its name with spaces ("send_polls" → "send polls"), so a new perk is never silently left out.
PERMISSION_WORDS = {
    "attach_files": "attach files and images",
    "add_reactions": "add reactions",
    "external_emojis": "use emoji from other servers",
    "use_external_emojis": "use emoji from other servers",  # another name discord.py has for the same permission
    "change_nickname": "change your nickname",
    "create_expressions": "add emojis and stickers",
    "create_instant_invite": "create invites",
    "send_tts_messages": "send text-to-speech messages",
    "move_members": "move people between voice channels",
}


def unlocked_permissions(rank: set[str], everyone: set[str], lower_ranks: Iterable[set[str]]) -> set[str]:
    """What a rank's role allows that you couldn't do before: its permissions, minus what @everyone already has,
    minus what any lower rank's role has (each ladder role carries its whole tier's perks, so the lower roles'
    perks aren't new). Server-wide only: a channel can still say otherwise, so the note never promises a channel."""
    already = set(everyone)
    for lower in lower_ranks:
        already |= lower
    return rank - already


def permission_words(permissions: set[str]) -> list[str]:
    """The permissions in everyday words, known ones in PERMISSION_WORDS order, then any others alphabetically.
    Two names for one permission only show once."""
    known = [words for name, words in PERMISSION_WORDS.items() if name in permissions]
    others = sorted(name.replace("_", " ") for name in permissions if name not in PERMISSION_WORDS)
    return list(dict.fromkeys(known + others))  # dict.fromkeys drops repeats and keeps the order


def and_list(words: list[str]) -> str:
    """["a", "b", "c"] → "a, b and c"."""
    if len(words) <= 1:
        return "".join(words)
    return ", ".join(words[:-1]) + " and " + words[-1]


def rank_up_note(progress: RankProgress, unlocked: set[str]) -> str:
    """The note itself. `progress` is worked out when the note is shown (not when they climbed), so a note that
    waited a few days still has the right XP to go. Plain bold names, not role mentions: it's a private note, and
    it's sent with pings switched off anyway.

    🎖️ You've climbed to **SWORN SWORDS**! 750 XP to **LORDS**.
    New with this rank: add emojis and stickers, create invites and send text-to-speech messages."""
    line = f"🎖️ You've climbed to **{tier_name(progress.tier)}**!"
    if progress.next_tier is None:
        line += " That's the top of the ladder, comrade."
    elif progress.to_go == 0:
        # Already enough XP for the next one too (say a VIP lowered the thresholds while the note waited)
        line += f" You already have the XP for **{tier_name(progress.next_tier)}**: it arrives with your next message."
    else:
        line += f" {progress.to_go:,} XP to **{tier_name(progress.next_tier)}**."
    words = permission_words(unlocked)
    if words:
        line += f"\nNew with this rank: {and_list(words)}."
    return line
