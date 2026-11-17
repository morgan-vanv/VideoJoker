"""/mc shout's rules: what it costs and how often you can do it. Pure Python, tested.

Shouting puts a message in every awake mode's chat, so two limits keep the game chat readable: one person can
shout once every 5 minutes, and anyone can shout at most once every 30 seconds. VIPs shout for free (still
within the limits). The USh goes to the bank: the first thing USh can be spent on.
"""

from typing import NamedTuple, Optional

SHOUT_COST = 50  # USh
PER_PERSON_SECONDS = 5 * 60
EVERYONE_SECONDS = 30
MAX_LENGTH = 200  # same as the booth's limit in booth/game.py


class Wait(NamedTuple):
    until: float  # when they can shout again (a time.time() number)
    everyone: bool  # True: someone else just shouted; False: it's their own cooldown


class Cooldowns:
    """Remembers the last shouts, in memory (a restart forgives everyone, which is fine)."""

    def __init__(self):
        self.last_by_person: dict[int, float] = {}
        self.last_anyone = 0.0

    def check(self, user_id: int, now: float) -> Optional[Wait]:
        """None if they may shout now, else how long they have to wait."""
        mine = self.last_by_person.get(user_id, 0.0) + PER_PERSON_SECONDS
        if now < mine:
            return Wait(mine, everyone=False)
        anyone = self.last_anyone + EVERYONE_SECONDS
        if now < anyone:
            return Wait(anyone, everyone=True)
        return None

    def shouted(self, user_id: int, now: float) -> None:
        self.last_by_person[user_id] = now
        self.last_anyone = now
