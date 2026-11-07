# OSRS linking + automated flexing — design

**Status:** proposal, nothing built yet (`feature/osrs-linking`). Written 2026-11-07 by Morgan + Claude.
Open questions are marked ❓. Once we agree, the answers move into this doc and `docs/decisions.md`.

## Why

Until 2026-11-06, `#automated-rs-flexing` worked like this: everyone pasted one shared Dink config URL into
RuneLite, that config held the channel's Discord webhook URL, and the config lived in a public GitHub file.
Someone found the webhook there and spammed the channel. A Discord webhook URL is a password that anyone can
post with, and sharing one password with 30 people means it eventually leaks.

The brief: bring flexing back with a **nicer, safer enrollment**, and make the bot the front door for the
OSRS side of the community: link your character, opt into flexing, and join the clan or the friends group.

## What we build vs. what we leave to others

| Job | Who does it | Why |
|---|---|---|
| Stats lookups, leaderboards, competitions, achievement and name-change broadcasts | **Wise Old Man's bot** (stays) | It already does these well, on WOM's own data. Rebuilding them is lots of work for a worse copy. |
| "Who is this Discord person in game?" | **VideoJoker** | Our bot is the only one that can *verify* it (see Dink below). WOM's `/setrsn` takes your word for it. |
| Joining the friends group on WOM | **VideoJoker** (automated) | Saves an admin from adding people by hand with the group's verification code. |
| Joining the in-game clan | **The game** (we point the way) | There's no API for it: Jagex only lets you apply from in game. |
| Drop and level flexing | **VideoJoker relays Dink** | Each person gets their own secret link, the real webhook never leaves the server, and the VJ can narrate. |

This lets the two bots complement each other: WOM shows numbers, the VJ handles people and flexing.

## The flow (`/osrs register`)

```
/osrs register name:<rsn>
  └─ the bot looks the name up on Wise Old Man (tracking it if it's new)
     "Found Swannobi: combat 126, total 2277. Is this you?"  [Yes] [No]
        └─ linked (unverified for now: it's the honor system until Dink proves it)
           "Want your drops flexed in #automated-rs-flexing?"  [Yes] [Not now]
              Yes → your personal Dink link + 3 steps (only you can see it)
           "Join the clan?"  [Yes] [No]  (skipped if they're already in the clan's WOM group)
              Yes → clan chat name + how to apply in game (+ ❓ ping a recruiter)
              No  → "Friend of the clan, then?"  [Yes] [No thanks]
                       Yes → added to the WOM friends group automatically
```

All of it is ephemeral (only the person sees it) and button-driven, like Three Card Monte. `/osrs me`
shows your card again with the same buttons, so nothing is a one-time chance.

## Commands (proposal)

| Command | Who | Does |
|---|---|---|
| `/osrs register name` | anyone | Link your character and run the flow above. Running it again changes the name. |
| `/osrs me` | anyone | Your card: RSN, verified ✓ or not, flexing on/off, clan/friends status, buttons to change any of it. |
| `/osrs flexing` | anyone | Show your Dink steps again, or **reset** your link if you leaked it (the old one dies instantly). |
| `/osrs unregister` | anyone | Forget me: removes the link and turns off flexing. |
| `/osrs whois member` | anyone | "@Frankie is morpheus_rs ✓". Handy, and it's the one lookup WOM's bot can't do. |
| `/osrs revoke member` | VIP | Kill someone's flexing link (spam, left the server). |

❓ `/osrs register` (one `/osrs` group) or your `/register-osrs`? A group keeps every OSRS command together
in Discord's command picker (type `/osrs` and they're all there). Teaching note: that's an
`app_commands.Group`, which would be a new discord.py idea for this repo.

## Dink: a personal link instead of a shared password

Dink (the RuneLite plugin) has a **Dynamic Config URL** setting: Dink downloads its whole configuration from
that URL on startup and again every few hours, *including webhook URLs*. That's what leaked last time, but
it's also the cleanest way to enroll people:

1. On "Yes, flex my drops", the bot makes a random secret (a **token**) for that person.
2. It shows them one URL to paste into Dink's *Dynamic Config URL*: `https://<bot host>/dink/<token>/config.json`.
3. The bot serves that URL: the community's standard Dink settings (loot threshold, pets, clogs, …, kept in
   the repo with no secrets) plus *their* webhook URL, `https://<bot host>/dink/<token>`, which points at
   **our bot**, not Discord.
4. Dink posts drops to the bot. The bot checks them and forwards good ones to `#automated-rs-flexing` through
   the real Discord webhook, which lives only in the server's `.env`.

What the bot checks on every message (Dink sends these fields with every notification):
- the **token** is known and not revoked (unknown → 404, nothing posted);
- **`playerName`** matches the linked RSN, or **`dinkAccountHash`** matches (that hash survives name changes);
- **`discordUser.id`**, which Dink sends by default when Discord is open: if present, it must be the person
  who enrolled;
- a rate limit per person (e.g. 20 posts a minute), so even a leaked link can't flood the channel.

The first message that passes marks the link **verified ✓**: it came from RuneLite, logged into that
character, on that person's Discord. That's real proof of ownership, with no codes to type.

Why this is safer than before:
- **No shared secret.** Each person has their own link. A leak affects one person, and `/osrs flexing reset` fixes it.
- **A leaked link still can't post as someone else**: wrong `playerName`/hash → rejected.
- **Central settings.** Changing the loot threshold for everyone is a commit to the repo's Dink settings file.
  Dink picks it up within a few hours.
- **The real webhook never leaves the server.**

Formats: Dink posts JSON, or `multipart/form-data` with a `payload_json` part and a `file` screenshot
(≤ 8 MB) when there's a screenshot. aiohttp (already installed with discord.py) reads both.

❓ **How should posts look?** (a) Forward Dink's own embed and screenshot through the webhook, exactly as
before. No new bot permissions. (b) The VJ rewrites it: *"Swannobi pulls Hydra leather from the
Alchemical Hydra! The crowd goes wild. 9.17M."* We can do (b) through the same webhook too, so it still
needs no new permissions. Suggestion: (b) for the headline with Dink's screenshot attached.

Migration for people with the old setup: replace the old Dynamic Config URL with the personal one, and tick
Dink's **Import Policy → Overwrite Webhooks**. By default Dink *merges* webhook lists, so the old dead URL
would stick around. (Worth crediting and looping in swannobi: their `Dink-Config` settings are the natural
starting point for our standard settings file.)

### Alternative we considered: Dink's official Webhook Filter
Dink's authors run a free filter service (and a self-hostable Cloudflare Worker) that sits in front of a
webhook and only lets allowlisted RSNs through. It needs no hosting from us, but everyone still shares one
URL, a spammer can fake an allowlisted name, and the allowlist is managed on their site, not by our bot.
It's a fine stopgap if the relay can't be hosted soon.

## Hosting (needs the homelab session)

The relay means the bot **receives** web requests for the first time:
- An `aiohttp.web` server inside the bot on an internal port (e.g. `8080`, set by `DINK_PORT`). UID 1000 can
  listen there; nothing is written to disk (screenshots stay in memory), so the read-only FS is fine.
- It needs to be reachable from the internet at a stable HTTPS address, e.g. `dink.morganvanv.com`, ideally
  through a Cloudflare Tunnel or Morgan's reverse proxy, so no port is opened on the router. That's server
  work for the homelab session, and it adds a 7th line to the hosting contract ("listens on DINK_PORT").
- If the relay isn't reachable yet, the bot keeps working and `/osrs flexing` says "coming soon".
  Registration and groups don't depend on it.

## Database (additive only: two new tables)

```sql
-- One row per linked character. Built for alts from day one, so they won't need a schema change later
-- (the hosting contract forbids changing existing columns). v1 only lets you have one.
CREATE TABLE IF NOT EXISTS osrs_accounts (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id        INTEGER NOT NULL,
    rsn               TEXT    NOT NULL,          -- as shown, e.g. "Swannobi"
    rsn_key           TEXT    NOT NULL UNIQUE,   -- lowercase, '-'/'_' -> ' ' (OSRS treats these as the same name)
    wom_player_id     INTEGER,                   -- WOM's id; survives name changes
    dink_account_hash TEXT,                      -- learned from the first Dink post; survives name changes
    verified_at       TEXT,                      -- when Dink proved ownership (NULL = honor system)
    is_default        INTEGER NOT NULL DEFAULT 1,
    created_at        TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Flexing enrollment. We store a *hash* of the token, never the token itself (same idea as passwords):
-- if the database file ever leaks, nobody can post with what's in it. That's also why a lost link is reset,
-- not shown again.
CREATE TABLE IF NOT EXISTS dink_links (
    account_id    INTEGER PRIMARY KEY REFERENCES osrs_accounts(id),
    token_sha256  TEXT NOT NULL UNIQUE,
    created_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_post_at  TEXT,
    revoked_at    TEXT
);
```

Clan and friends-group membership isn't stored: Wise Old Man is the source of truth, so the bot asks it.

## External APIs

**Wise Old Man** (`https://api.wiseoldman.net/v2`), through aiohttp:
- `POST /players/:username`: track or update a player (creates their WOM profile if new), used on register.
- `GET /groups/:id`: members of the clan group and the friends group, to skip questions people have already answered.
- `POST /groups/:id/members` with `verificationCode` + `members: [{username, role}]`: add to the friends group.
- Rate limits: 20 requests/min without an API key, 100 with one (free, by asking in WOM's Discord).
  Plenty for registrations. Send a descriptive `User-Agent` (e.g. `VideoJoker Discord bot (github.com/morgan-vanv/VideoJoker)`);
  WOM says it will IP-ban unidentified abusers.
- Secrets in `.env`: `WOM_FRIENDS_GROUP_ID`, `WOM_FRIENDS_VERIFICATION_CODE`, `WOM_CLAN_GROUP_ID`, optional `WOM_API_KEY`.

**Dink**: see above. Secrets in `.env`: `DINK_DISCORD_WEBHOOK_URL` (the real one, made fresh), `DINK_PUBLIC_URL`.

**OSRS Wiki prices API**: not needed for v1 (Dink already sends item prices). Noted for later ("what's this worth?").

## Discord permissions and intents
- Nothing new for register/groups/flexing-through-webhook: ephemeral replies need no channel permissions,
  and webhook posts need none either. `Intents.default()` is enough.
- ❓ Optional extras that **would** need more: giving "Clan" / "Friend of the clan" Discord roles
  (Manage Roles → re-invite), or pinging a recruiter role when someone wants to join (an exception to the
  bot-wide "no role pings" rule, for that one message).

## Code layout (when we build it)

```
cogs/osrs.py         /osrs commands (thin)
osrs/accounts.py     RSN normalising + validation (pure Python, tested)
osrs/wom.py          tiny Wise Old Man client (aiohttp, User-Agent, handles 429)
osrs/dink.py         the relay: aiohttp.web routes, payload checks (pure checks are tested)
osrs/dink_config.json  the community's standard Dink settings (no secrets)
osrs/ui.py           the register flow's buttons (Views)
osrs/lines.py        the VJ's copy
core/database.py     the two new tables + queries (with tests, as always)
```

## Shipping order (each PR safe to merge on its own)
1. **Register + WOM groups**: tables, `/osrs register|me|unregister|whois`, the friends-group join, the clan
   pointer. No hosting changes. If Morgan wants to write part of it, `osrs/accounts.py` and the table
   queries are a good first piece.
2. **Flexing relay**: the web server, personal links, verification, `/osrs flexing`, `/osrs revoke`. Merges
   once the homelab side has the public address ready.
3. Later ideas: alts, VJ roasts for deaths, USh rewards for drops, a "biggest drop this week".

## Open questions
1. ❓ `/osrs register` group, or `/register-osrs`?
2. ❓ The friends group: does anyone who asks get added straight away, or should a VIP approve?
3. ❓ The clan "Yes": just show the clan chat name and how to apply, or also notify recruiters (role ping)?
4. ❓ Post style for flexing: Dink's embed as before, or the VJ narrating with the screenshot?
5. ❓ Discord roles for Clan / Friend of the clan (needs Manage Roles)?
6. ❓ Hosting the relay: OK to expose it via a Cloudflare Tunnel on your server (`dink.morganvanv.com`)? Until
   then, use Dink's official Webhook Filter as a stopgap?
7. ❓ Alts: one character per person for v1 (the schema is ready for more)?
