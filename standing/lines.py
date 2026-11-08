"""The VJ's narration for XP, ranks, USh and the leaderboard. Every member-facing line for /rank, /balance, /pay
and /leaderboard lives here, so the voice stays in one place (same idea as personal_vc/lines.py).

The "how you earn" line is built from the numbers in core/database.py, so it can never drift from what the bot
actually hands out: change XP_PER_COMMAND there and /rank, /balance, /leaderboard and /ladder show all follow.
"""

from typing import Callable, Optional

from discord.utils import escape_markdown

from core.database import COMMAND_XP_COOLDOWN_SECONDS, USH_PER_MESSAGE, XP_PER_COMMAND, XP_PER_MESSAGE, UshMove
from ranks.ladder import RankProgress, Tier, progress_bar
from standing.board import Placing

# How to show a rank: the cog passes a function that turns a tier into its role mention (embeds show a mention as
# the role's coloured pill and never ping), so these lines don't need to know about Discord servers.
Label = Callable[[Tier], str]


def cooldown_words(seconds: int) -> str:
    """60 → "once a minute", 120 → "once every 2 minutes", 45 → "once every 45 seconds"."""
    if seconds % 60 == 0:
        minutes = seconds // 60
        return "once a minute" if minutes == 1 else f"once every {minutes} minutes"
    return f"once every {seconds} seconds"


def earning_line() -> str:
    """The one sentence that explains how XP and USh are earned (footers of /rank, /balance, /leaderboard and
    /ladder show)."""
    return (
        f"Every message: {XP_PER_MESSAGE} XP + {USH_PER_MESSAGE} USh. "
        f"Every command: {XP_PER_COMMAND} XP ({cooldown_words(COMMAND_XP_COOLDOWN_SECONDS)})."
    )


EARNING = earning_line()

USH_EXPLAINED = (
    f"USh (Ugandan shillings) is the VJ's play money. Every message you send earns {USH_PER_MESSAGE}, "
    "and `/pay` sends some to another member."
)

# ---- /rank (and the "you are here" bit of /ladder show)

RANK_TITLE = "🎬 Now showing: {name}"
RANK_BOT = "🎞️ Bots don't climb the ladder, comrade. They just run the projector."
RANK_POINTER = "Everyone's standings: `/leaderboard` · USh and payments: `/balance`"
BREAKDOWN_HEADING = "Where the XP came from"
TOP_OF_THE_LADDER = "🏆 Top of the ladder. Nowhere left to climb, comrade."
YOU_ARE_HERE = "📍 You are here"


def rank_line(progress: RankProgress, label: Label) -> str:
    if progress.tier is None:
        return "**Rank:** none yet"
    return f"**Rank:** {label(progress.tier)}"


def progress_line(progress: RankProgress, label: Label) -> str:
    """▰▰▰▰▰▰▱▱▱▱ 612 / 1,000 XP · 388 to LORDS (or the top-of-the-ladder line)."""
    if progress.next_tier is None:
        return TOP_OF_THE_LADDER
    goal = progress.next_tier.min_xp
    bar = progress_bar(progress.xp, goal)
    if progress.to_go == 0:
        # Enough XP, but the role isn't on yet (say the ladder was off for a while): the next XP brings it
        return f"{bar} {label(progress.next_tier)} earned: it arrives with your next message."
    return f"{bar} {progress.xp:,} / {goal:,} XP · {progress.to_go:,} to {label(progress.next_tier)}"


def xp_line(total: int, placing: Optional[Placing], on_board: Optional[int]) -> str:
    """**XP:** 612 · #7 of 143 on this server. on_board is None outside a server (in DMs), so no place at all."""
    line = f"**XP:** {total:,}"
    if placing is not None:
        line += f" · #{placing.place} of {on_board:,} on this server"
    elif on_board is not None:
        line += " · not on this server's board yet: one message gets you on"
    return line


def ush_line(balance: int) -> str:
    return f"**USh:** {balance:,}"


def you_are_here(progress: RankProgress, label: Label) -> str:
    """For /ladder show: your rank and XP, then how far the next rank is."""
    return f"{rank_line(progress, label)} · {progress.xp:,} XP\n{progress_line(progress, label)}"


# ---- /balance

BALANCE_TITLE = "📼 {name}'s USh"
BALANCE_BOT = "🎞️ Bots don't carry USh, comrade. The projector runs for free."
PAYMENTS_HEADING = "Last payments"
NO_PAYMENTS = "No payments yet."
PAY_HINT = "Send some with `/pay`."


def balance_line(balance: int) -> str:
    return f"**{balance:,} USh**"


def who(user_id: Optional[int]) -> str:
    """The other side of a payment: a mention (fine inside an embed, embeds never ping), or the bank."""
    return "the bank" if user_id is None else f"<@{user_id}>"


def move_line(move: UshMove, viewer_id: int) -> str:
    """➡️ Sent **50 USh** to @Bob · "popcorn" · 2 hours ago. <t:…:R> is Discord's own timestamp: every reader
    sees it as "2 hours ago" in their own language, and it keeps itself up to date."""
    if move.from_user_id == viewer_id:
        line = f"➡️ Sent **{move.amount:,} USh** to {who(move.to_user_id)}"
    else:
        line = f"⬅️ Got **{move.amount:,} USh** from {who(move.from_user_id)}"
    if move.note:
        # escape_markdown: a note is someone else's text, so it can't turn into bold, links or a giant heading
        line += f' · "{escape_markdown(move.note)}"'
    return f"{line} · <t:{move.created_at}:R>"


def balance_pointer(xp_total: int, rank: Optional[str]) -> str:
    """📼 612 XP · @SWORN SWORDS · the full picture in `/rank`"""
    parts = [f"{xp_total:,} XP"] + ([rank] if rank else [])
    return "📼 " + " · ".join(parts) + " · the full picture in `/rank`"


# ---- /pay

PAY_SELF = "🎬 Cut! You can't pay yourself, comrade: that's just moving USh from one pocket to the other."
PAY_BOT = "🎬 Cut! Bots can't hold USh, comrade: it would vanish into the projector. Pay a person instead."
PAY_SHORT = "📼 Not enough USh, comrade: you have **{balance} USh**, and that payment needs **{amount} USh**."
PAY_JAMMED = "🎞️ The projector jammed and no USh moved. Try again in a moment."


def pay_done(sender: str, recipient: str, amount: int, note: Optional[str]) -> str:
    """🎬 @Alice sent **50 USh** to @Bob. Plus the note, if there is one."""
    line = f"🎬 {sender} sent **{amount:,} USh** to {recipient}."
    if note:
        line += f'\n📝 "{escape_markdown(note)}"'
    return line


# ---- /leaderboard

BOARDS = ("xp", "ush")  # the two boards, in button order
BOARD_TITLES = {"xp": "🏆 Leaderboard: XP", "ush": "🏆 Leaderboard: USh"}
UNITS = {"xp": "XP", "ush": "USh"}
NOT_ON_BOARD = {
    "xp": "You're not on this board yet: one message gets you on.",
    "ush": f"You have no USh yet: every message earns {USH_PER_MESSAGE}.",
}
BOARD_EMPTY = "🎞️ Nobody's on this board yet. The reel is blank, comrade: start chatting."
MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}


def place_label(place: int) -> str:
    return MEDALS.get(place, f"`#{place}`")


def board_row(row: Placing, unit: str, is_you: bool) -> str:
    """🥇 @Morgan · 4,210 XP, in bold with "← you" if it's the person who asked."""
    text = f"{place_label(row.place)} <@{row.user_id}> · {row.score:,} {unit}"
    return f"**{text}** ← you" if is_you else text


def board_count(count: int) -> str:
    return "1 comrade on the board." if count == 1 else f"{count:,} comrades on the board."
