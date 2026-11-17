"""Every line raffles show, kept in one place.

Plain on purpose (Morgan, 2026-11-16): short, clear lines without the VJ narration. The winner line is Morgan's words.

{prize} is what the host typed, with any * or _ in it shown as typed (see prize()). Times are Discord time stamps
(<t:...>), so everyone sees them in their own time zone: R counts down ("in 2 hours"), f is the date and time
("November 18, 2026 6:45 PM").
"""

from datetime import datetime

import discord

from raffle.rules import LONGEST, MOST_WINNERS, TICKET


def stamp(when: datetime, style: str) -> str:
    return f"<t:{int(when.timestamp())}:{style}>"


def prize(text: str) -> str:
    """The prize in bold, with any * or _ in it shown as typed instead of turning into formatting."""
    return f"**{discord.utils.escape_markdown(text)}**"


def names(mentions: list[str]) -> str:
    """'@A', '@A and @B', '@A, @B and @C'"""
    if len(mentions) <= 1:
        return "".join(mentions)
    return f"{', '.join(mentions[:-1])} and {mentions[-1]}"


def winner_count(count: int) -> str:
    return "1 winner" if count == 1 else f"{count} winners"


# ---- The raffle card (an embed; mentions in it show as names but never ping)

TITLE_RUNNING = f"{TICKET} Raffle"
TITLE_OVER = f"{TICKET} Raffle over"
TITLE_CANCELLED = f"{TICKET} Raffle cancelled"

PRIZE_LINE = "Prize: {prize}"
ENTER = f"React with {TICKET} to enter."
ENDS = "Ends {relative} ({at})"
HOSTED = "Hosted by {host} · {winners}"
HOSTED_PLAIN = "Hosted by {host}"

WINNER = "**Winner:** {winners}"
WINNERS = "**Winners:** {winners}"
NO_ENTRIES = "No one entered, so there's no winner."
ENTRIES = "{count} entries · Ended {at}"
ONE_ENTRY = "1 entry · Ended {at}"
CANCELLED_BY = "Cancelled by {who}. No winner was drawn."

# ---- Posted under the card when it's drawn (the winner line pings the winners, and only them)

WON = "Congratulations {winners} you just won: {prize}"
NOBODY_WON = "No one entered the raffle for {prize}, so there's no winner."

# ---- Replies only the person who ran the command sees

STARTED = (
    "Your raffle is up. It ends {relative}. `/raffle end` draws the winner early, and `/raffle cancel` calls it off."
)
BAD_DURATION = "I couldn't read **{text}** as a length of time. Try something like `30m`, `2h` or `1d 12h`."
TOO_SHORT = "A raffle has to run for at least a minute."
TOO_LONG = f"A raffle can run for {LONGEST.days} days at most."
ALREADY_RUNNING = (
    "You already have a raffle running in this server: {link}\nEnd it or cancel it before starting another."
)
START_FAILED = "I couldn't post the raffle here just now. Try again in a moment."
CANT_HERE = "I can't run a raffle in this channel. I need **{missing}** here."

NONE_RUNNING = "You don't have a raffle running in this server."
NOT_RUNNING = "That raffle isn't running any more."
NOT_YOURS = "Only the host or a VIP can do that."
CANCELLED = "Raffle cancelled: {prize}"
DRAWN = "Done. The result is posted under the raffle: {link}"
GONE = "The raffle's message is gone (deleted?), so I've closed that raffle."
TRY_AGAIN = "I couldn't reach the raffle's message just now. Try again in a moment."

# ---- Command descriptions (Discord shows these in the / menu)

GROUP = "Give something away: people react to enter, and a winner is drawn."
START = "Start a raffle in this channel"
START_PRIZE = "What the winner gets"
START_DURATION = f"How long it runs, like 30m, 2h or 1d ({LONGEST.days} days at most)"
START_WINNERS = f"How many winners to draw (1 to {MOST_WINNERS})"
CANCEL = "Call off a raffle without drawing a winner"
END = "End a raffle now and draw the winner"
WHICH = "Which raffle (leave empty for yours). VIPs can pick anyone's."
# A suggestion in the "which raffle" list
CHOICE = "{prize} (hosted by {host})"
