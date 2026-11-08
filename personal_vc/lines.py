"""The VJ's narration for personal voice channels. Every user-facing line lives here, so the voice stays in one
place (same idea as music/lines.py)."""

from typing import Optional

from personal_vc.rules import Mode

# Morgan's wording, word for word: above the buttons in every new channel's chat
PANEL = "It's your space, so you set the rules -- have fun being mysterious."

MODE_LABELS = {Mode.OPEN: "🔓 open", Mode.LOCKED: "🔒 locked", Mode.HIDDEN: "👻 hidden"}

WELCOME = "🎬 {owner}, this channel is yours until the last person walks out."

MODE_SET = {
    Mode.OPEN: "🔓 Doors open. Anyone can see it, anyone can walk in.",
    Mode.LOCKED: "🔒 Locked. Everyone can see the screen, only your guests get a seat. Whoever's inside stays.",
    Mode.HIDDEN: "👻 Hidden. Only your guests even know this cinema exists. Very mysterious.",
}
MODE_FAILED = "🎞️ Discord wouldn't let me change your voice channel's settings. A mod can check the bot log."

# {hub} is the lobby as a channel mention (<#id>), never its name: Discord shows it as a link, and it stays right
# if a mod renames the channel
NOT_HERE = "These buttons work in your own channel's chat, comrade. Join {hub} to get one."
NOT_YOURS = "🎞️ Not your voice channel, comrade: it belongs to {owner}. Want your own? Join {hub}."
SWITCHED_OFF = "🎞️ Personal channels are switched off here. A VIP can bring them back with `/personalvc setup`."

LET_IN_PROMPT = "🎟️ Who's on the guest list? Pick them below. They stay on it for next time too."
LET_IN_PLACEHOLDER = "Pick your guests"
LET_IN_DONE = "🎟️ {names} on the guest list. When you lock up, the door still opens for them."
LET_IN_NOBODY = "🎟️ Nobody new to add. (The owner and bots don't need tickets; the rest were already on it.)"
LIST_FULL = "🎟️ The guest list holds {limit} people and that would make {total}. ➖ Remove someone first."

REMOVE_PROMPT = "🚪 Who's off the list? Nobody gets thrown out; the door just won't open for them again."
REMOVE_PLACEHOLDER = "Pick who to take off"
REMOVE_DONE = "🚪 {names} off the guest list."
NO_GUESTS = "🚪 Your guest list is empty, comrade. ➕ Let in someone first."
UNKNOWN_GUEST = "Someone who left the server ({user_id})"

PICK_EXPIRED = "📼 That list closed. Press the button again."

# /personalvc
SETUP_DONE = "🎬 Personal channels are rolling, comrade. Join the lobby and the VJ hands you your own screen."
SETUP_NEEDS_CATEGORY = (
    "🎬 Cut! The lobby must sit inside a category (like **personal channels**): new channels go there, and "
    "that's the only place I need the extra permissions."
)
SETUP_BAD_STAFF = "🎬 Cut! @everyone can't be the staff role, or every hidden channel would be on the big screen."
NOT_SET_UP = "🎞️ No personal channels on this reel yet. A VIP can switch them on with `/personalvc setup`."
SWITCHED_OFF_DONE = (
    "📼 Personal channels are off. Channels already open stay until they empty out, and everyone's saved mode "
    "and guest list are kept for next time."
)


def names_list(names: list[str]) -> str:
    """Bob · Alice · Frankie: short enough to read in one go."""
    return " · ".join(names)


def guest_count(count: int) -> str:
    if count == 0:
        return "nobody on the list"
    return "1 guest on the list" if count == 1 else f"{count} guests on the list"


def welcome_back(name: str, mode: Mode, guests: int) -> Optional[str]:
    """The extra welcome line when someone's saved settings were put on their new channel, or None when there
    was nothing to put on (open, and nobody on the list: just a normal channel)."""
    if mode is Mode.OPEN and guests == 0:
        return None
    return f"Back again, {name}. Your channel stays {MODE_LABELS[mode]}, {guest_count(guests)}."
