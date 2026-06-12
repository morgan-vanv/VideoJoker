import random

def deal_winning_card() -> str:
    """Deals the winning card for Three Card Monte."""
    return random.choice(["A", "B", "C"])
