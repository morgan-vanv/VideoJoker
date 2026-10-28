"""Tests for core/database.py, run against a throwaway SQLite file (see the `db` fixture)."""
import pytest

from core.database import Database
from tests.conftest import OWNER_ID

ALICE, BOB = 1, 2  # fake Discord user ids


# ---- Roles (VIP / BANNED) ----

async def test_owner_is_vip_from_the_start(db):
    assert OWNER_ID in db.vips


async def test_owner_cannot_be_banned(db):
    with pytest.raises(ValueError):
        await db.set_user_role(OWNER_ID, "BANNED")
    assert OWNER_ID not in db.banned


async def test_unknown_role_is_rejected(db):
    with pytest.raises(ValueError):
        await db.set_user_role(ALICE, "ADMIN")


async def test_vip_and_banned_are_mutually_exclusive(db):
    await db.set_user_role(ALICE, "VIP")
    await db.set_user_role(ALICE, "BANNED")
    assert ALICE in db.banned and ALICE not in db.vips

    await db.set_user_role(ALICE, "VIP")
    assert ALICE in db.vips and ALICE not in db.banned


async def test_reset_returns_user_to_normal_but_owner_stays_vip(db):
    await db.set_user_role(ALICE, "BANNED")
    await db.remove_user_role(ALICE)
    assert ALICE not in db.banned and ALICE not in db.vips

    await db.remove_user_role(OWNER_ID)
    assert OWNER_ID in db.vips


async def test_roles_survive_a_restart(db, tmp_path):
    # The in-memory cache is rebuilt from the database file on startup
    await db.set_user_role(ALICE, "VIP")
    await db.set_user_role(BOB, "BANNED")

    restarted = Database(db_path=tmp_path / "test.db")
    await restarted.setup()
    try:
        assert ALICE in restarted.vips
        assert BOB in restarted.banned
    finally:
        await restarted.close()


# ---- Economy (USh) ----

async def test_new_users_start_with_zero_balance(db):
    assert await db.get_balance(ALICE) == 0


async def test_add_balance_creates_then_adds_up(db):
    await db.add_balance(ALICE, 1)
    await db.add_balance(ALICE, 1)
    await db.add_balance(ALICE, 5)
    assert await db.get_balance(ALICE) == 7


async def test_transfer_moves_money(db):
    await db.add_balance(ALICE, 10)
    assert await db.transfer_balance(ALICE, BOB, 4) is True
    assert await db.get_balance(ALICE) == 6
    assert await db.get_balance(BOB) == 4


async def test_transfer_with_insufficient_funds_changes_nothing(db):
    await db.add_balance(ALICE, 3)
    assert await db.transfer_balance(ALICE, BOB, 4) is False
    assert await db.get_balance(ALICE) == 3
    assert await db.get_balance(BOB) == 0


async def test_transfer_from_a_user_with_no_account_fails(db):
    assert await db.transfer_balance(ALICE, BOB, 1) is False
    assert await db.get_balance(BOB) == 0


async def test_transfer_of_entire_balance_is_allowed(db):
    await db.add_balance(ALICE, 5)
    assert await db.transfer_balance(ALICE, BOB, 5) is True
    assert await db.get_balance(ALICE) == 0


# ---- XP ----

async def test_server_and_bot_xp_are_counted_separately(db):
    assert await db.get_xp(ALICE) == (0, 0)
    await db.add_server_xp(ALICE)
    await db.add_server_xp(ALICE)
    await db.add_bot_xp(ALICE)
    assert tuple(await db.get_xp(ALICE)) == (2, 1)


# ---- Reaction roles (database layer only; the commands are still a stub for the crew) ----

async def test_reaction_role_lookup_and_overwrite(db):
    assert await db.get_reaction_role(555, "🎮") is None
    await db.add_reaction_role(555, "🎮", 42)
    assert await db.get_reaction_role(555, "🎮") == 42
    await db.add_reaction_role(555, "🎮", 43)  # same message + emoji: the role is replaced
    assert await db.get_reaction_role(555, "🎮") == 43


@pytest.mark.parametrize("amount", [0, -50])
async def test_transfer_rejects_zero_and_negative_amounts(db, amount):
    # /pay already refuses these, but the database must too: a negative transfer
    # would otherwise move money backwards (from the receiver to the sender).
    await db.add_balance(ALICE, 10)
    assert await db.transfer_balance(ALICE, BOB, amount) is False
    assert await db.get_balance(ALICE) == 10
    assert await db.get_balance(BOB) == 0
