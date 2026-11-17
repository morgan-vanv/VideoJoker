"""Tests for /profile's lines (standing/lines.py) and the accounts dropdowns (core/accounts_view.py). /profile
took over /rank, /balance, /userinfo and /ladder show on 2026-11-16."""

from core.accounts_view import AccountChoice, AccountsView
from ranks.ladder import Tier
from standing import lines

TIERS = [Tier(3, 30, 5000), Tier(1, 10, 1), Tier(2, 20, 1000)]


def label(tier: Tier) -> str:
    return f"<@&{tier.role_id}>"


def test_the_ladder_reads_bottom_up_with_your_rank_pinned():
    text = lines.ladder_line(TIERS, TIERS[2], label)
    assert text == "<@&10> 1 XP → **<@&20> 1,000 XP** 📍 → <@&30> 5,000 XP"


def test_no_rank_yet_means_no_pin():
    assert "📍" not in lines.ladder_line(TIERS, None, label)


def test_plays_and_around_lines():
    assert lines.plays_line("OSRS", ["Zezima ⭐", "ZezIron"]) == "**OSRS:** Zezima ⭐, ZezIron"
    assert lines.around_line(100, 200) == "On Discord since <t:100:D> · here since <t:200:D>"
    assert lines.around_line(100, None) == "On Discord since <t:100:D>"  # in DMs, or they've left the server


async def nothing(_interaction, _value):
    return None


async def test_one_account_gets_only_the_unlink_dropdown():
    view = AccountsView([AccountChoice("zezima", "Zezima", True)], nothing, nothing)
    assert [item.placeholder for item in view.children] == ["Unlink one…"]


async def test_the_main_dropdown_offers_only_the_other_accounts():
    choices = [AccountChoice("zezima", "Zezima", True), AccountChoice("zeziron", "ZezIron", False)]
    view = AccountsView(choices, nothing, nothing)
    main, unlink = view.children[0], view.children[1]
    assert [option.value for option in main.options] == ["zeziron"]
    assert [option.value for option in unlink.options] == ["zezima", "zeziron"]
