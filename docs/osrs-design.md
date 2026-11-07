# OSRS linking + automated flexing — design

**Status:** v1 built on `feature/osrs-linking` (PR #65), awaiting a dev-bot test. Written 2026-11-07 by Morgan + Claude,
revised after Morgan's feedback the same night.

## Why

Until 2026-11-06, `#automated-rs-flexing` worked like this: everyone pasted one shared Dink config URL into
RuneLite, and that config, a public GitHub file, contained the channel's Discord webhook URL. Someone found it
and spammed the channel. A Discord webhook URL works like a password: anyone holding it can post.

The brief: bring flexing back with **easy enrollment** and the webhook **out of public view**, and let people
link their OSRS accounts (alts included) to their Discord so everyone knows who's who.

We trust everyone in the server. So there's no ownership verification: you type your names, the bot believes you.

## What we build vs. what we leave to others

| Job | Who | Why |
|---|---|---|
| Stats, leaderboards, competitions, achievement posts | **Wise Old Man's bot** (stays) | It does these well already. |
| "Which RSNs does this Discord person play?" | **VideoJoker** | `/osrs whois`, alts included. |
| Joining the in-game clan | **The game** | No API exists; the bot tells you how to apply. |
| Flexing setup and webhook safety | **VideoJoker** | Hands out the webhook privately; can swap it in seconds if it leaks. |
| Friends-of-the-clan WOM group | *parked* | Maybe later. |

## Commands (`/osrs` group)

| Command | Who | Does |
|---|---|---|
| `/osrs register rsn` | anyone | Adds an account to your Discord (as many as you like). Your first one is your default. Then it may ask the clan question and offer flexing (below). |
| `/osrs accounts` | anyone | Lists your accounts; ⭐ marks the default. |
| `/osrs default rsn` | anyone | Picks your default (autocompletes from your accounts). |
| `/osrs remove rsn` | anyone | Unlinks an account (autocompletes). |
| `/osrs whois member` | anyone | "@Frankie plays: ⭐ morpheus_rs, Iron Morph, Frank Tank". |
| `/osrs flexing` | anyone | Your flexing kit (what to paste into Dink), privately. Also enrolls you, so you get pinged if the link changes. |
| `/osrs rotate-webhook` | VIP | Leak response: deletes the flexing webhook (spam stops at once), makes a fresh one with the same name and picture, and pings everyone enrolled to run `/osrs flexing` again. |

Teaching note: a command group is an `app_commands.Group`, which is new for this repo. Typing `/osrs` in
Discord shows the whole family. Autocomplete (`@...autocomplete`) is new too: Discord asks the bot for
suggestions as you type.

## The register flow

```
/osrs register rsn:"Iron Morph"
  "📼 The VJ adds Iron Morph to your tapes."
  1. Flexing, ONLY if you haven't got the kit yet:
       "Want your drops flexed in #automated-rs-flexing?"   [Set me up]  [Not now]
  2. Deaths, ONLY after "Set me up", and only if a deaths channel is set:
       "And your deaths? Want them in #everyone-point-and-laugh?"   [Shame me]  [Keep my dignity]
     → the flexing kit, matching that answer (same as /osrs flexing)
  3. Clan, ONLY while none of your accounts is in the clan:
       "Is Iron Morph joining the clan?"   [Join the clan]  [Already a member]  [No thanks]
         Join             → join the "Ugandans" clan chat in game and apply
         Already a member → noted; you won't be asked again
         No thanks        → noted for this account
```
(Order changed 2026-11-07: flexing → deaths → clan, so the death notifications restored from the old setup sit
next to the flexing setup.)

"In the clan" means: you said "Already a member" for any of your accounts, **or** any of your accounts is
in the clan's Wise Old Man group, which syncs with the in-game clan by itself. The bot reads that group from
WOM, a public read with no key needed. If WOM is down or not configured, it just asks.

Everything is ephemeral (only you see it) and uses buttons, like Three Card Monte.

## Flexing: paste-it, with the webhook kept out of public view

The flexing kit, shown privately by `/osrs flexing`:

1. Dink settings → **Primary Webhook URLs**: delete anything there, paste `<the webhook URL>`.
2. **Webhook Overrides**: paste the deaths webhook into *Death Webhook Override* (if a deaths channel is set),
   otherwise make sure every override box is empty. (Dink *merges* webhook lists on import, so old URLs linger
   unless people clear them.)
3. Advanced → **Dynamic Config URL**: replace what's there with
   `https://raw.githubusercontent.com/morgan-vanv/VideoJoker/main/osrs/dink-settings.json`

**Deaths are opt-in per player.** They post in their own channel (`#everyone-point-and-laugh`) through a second
bot-owned webhook named "sit, respectfully", after the old one, with a banshee pointing and laughing as its picture (the flexing webhook has the old flexing gnome; both in `osrs/avatars/`). "Shame me" → the kit says to tick Dink's
*Enable Death* and paste the deaths URL into *Death Webhook Override*. "Keep my dignity" → the kit says to untick
*Enable Death*. For that reason `deathEnabled` is **not** in the shared settings file: Dink re-imports the shared
settings every few hours and would switch deaths back on for people who said no (a test enforces this). The
rest of swannobi's death settings (message, min value, PvP) stay shared.

Why separate pastes? The **settings** (loot threshold, which notifiers, screenshots…) are the same for everyone and
contain nothing secret, so they live in our public repo (`osrs/dink-settings.json`, swannobi's `Dink-Config` minus
its webhook keys, credited), and changing them is a normal PR. Dink re-reads them on
start and every few hours. The **webhook URL** is the secret, so it only ever appears in your private message.
Dink keeps the URL you pasted, because the settings file contains no webhook keys. A test in `tests/` fails if
anyone ever adds one, so this leak can't happen again from our repo.

### The bot owns the webhook
- The bot creates the webhook in the flexing channel itself (needs **Manage Webhooks**) and asks Discord for
  its URL when someone runs `/osrs flexing`. The URL isn't stored in `.env` or the database. Discord is the only
  place it lives.
- `/osrs rotate-webhook` (VIP): delete → recreate (copying the name and avatar) → post one message in the flexing
  channel pinging enrolled members: "The projector got a new bulb. Run `/osrs flexing` for the new link, comrades."
- The enrolled list exists only for those pings. Nothing else is tracked.

### Later, maybe: a relay + VJ narration
To *narrate* drops, the bot has to see them. That means Dink posts to the bot (a relay), which needs a public
HTTPS address on Morgan's server. Reading the channel instead would need the privileged Message Content intent,
which is against the hosting contract. Parked until the narration pitch wins Morgan over.

## Database (additive only: two new tables)

```sql
CREATE TABLE IF NOT EXISTS osrs_accounts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id  INTEGER NOT NULL,
    rsn         TEXT    NOT NULL,           -- as typed, e.g. "Iron Morph"
    rsn_key     TEXT    NOT NULL UNIQUE,    -- lowercase, '-' and '_' -> ' ': OSRS treats "Iron_Morph" = "iron morph"
    is_default  INTEGER NOT NULL DEFAULT 0,
    clan_answer TEXT,                       -- NULL (not asked) / 'joining' / 'member' / 'no'
    created_at  TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS osrs_flexers (   -- who to ping when the webhook is rotated
    discord_id  INTEGER PRIMARY KEY,
    enrolled_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```
`rsn_key` is UNIQUE, so two people can't both claim "Swannobi" (the second gets told who has it).
RSN check: 1–12 characters, letters, digits, spaces, `-` and `_` (OSRS's own rules). We don't check that the
account exists; we trust people.

## Config
- `.env`: `OSRS_FLEXING_CHANNEL_ID` (the channel drops post in) and, optionally, `OSRS_DEATHS_CHANNEL_ID`.
  The old setup sent deaths to their own channel through Dink's *Death Webhook Override*. If this is set,
  the bot makes a second webhook there and the kit includes that paste too.
- In code, not `.env` (same for dev and prod): the clan's WOM group, 7117 (`osrs/wom.py`), and the clan name and
  how to join ("join the **Ugandans** clan chat and apply"), which live in `osrs/lines.py` as the VJ's copy.

## Permissions and hosting contract
- **New permission: Manage Webhooks** (add it to the prod invite). Nothing else: ephemeral replies need no
  channel permissions, and pinging *users* is allowed (the bot-wide rule only blocks @everyone/roles).
- `Intents.default()`, no new port, no file writes, additive tables. The rest of the contract is unchanged.
- Wise Old Man: one `GET /groups/:id` per check, cached a few minutes, with a descriptive User-Agent (WOM asks
  for one). 20 requests/min without a key is plenty.

## Code layout
```
cogs/osrs.py              the /osrs group (thin)
osrs/accounts.py          RSN validation + normalising (pure Python, tested)
osrs/wom.py               tiny Wise Old Man client: "who's in the clan group?" (aiohttp, cached)
osrs/flexing.py           find/create/rotate the webhook; the flexing kit text
osrs/ui.py                the register flow's buttons (Views)
osrs/lines.py             the VJ's copy, clan join instructions
osrs/dink-settings.json   community Dink settings, served raw from GitHub (no secrets, test-enforced)
core/database.py          the two tables + queries (tested)
```
Plus `osrs/**` in `release.yml` paths, the README command list, SETUP_GUIDE (the env vars), and the invite permission.

## Parked / later
Ugandans Extended Universe (friends WOM group) auto-join · relay + narrated drops · a ✓ for accounts seen via Dink
(only if it's free) · USh for big drops · "biggest drop this week".
