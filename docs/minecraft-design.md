# Minecraft ↔ Discord: design

**Status:** part 1 (linking, status, marquee, welcome) built on `feature/minecraft`. Part 2 (the booth: `/mc shout`,
the in-game Discord nudge, Factions postcards) designed here, waiting on the infra side. Written 2026-11-15 by
Morgan + Claude, the day the Minecraft network went live at `mc.morganvanv.com`.

## Why

The Minecraft network is back (digital-infrastructure, `docs/runbooks/games.md`): a Velocity proxy with Geyser
(Java and Bedrock), a hub, and three modes: **Factions** (the forever world from the old factions server),
**Anarchy** (pure vanilla, hard, never rolled back) and **Creative** (plots, waiting on PlotSquared). Morgan's
brief: **the server funnels people to the Discord, and the Discord funnels people to the server.**

## Morgan's calls (2026-11-15)

- **Trust, like OSRS.** You type your name, the bot believes you. Linking grants nothing in game today. Later,
  maybe: XP in Discord for feats in Minecraft or OSRS (parked, below).
- **A bridge into the server is fine** if it's secure and does what we need (part 2's booth).
- **New channels for it**, made by Morgan from a checklist (below), no new bot permissions.
- **Postcards for Factions only.** Anarchy stays pure vanilla and raw: no postcards from it.
- **`/mc shout` and the in-game "join the Discord" nudge reach Factions and Anarchy** (plain vanilla chat
  messages, no plugin). `/mc shout` costs USh (VIPs free): the first real USh sink.
- **Wanted:** the marquee, the cast list (`/mc whois`, `/mc who`), postcards, `/mc shout` ASAP.
  **Later / to discuss:** VJ-written server-list text, rank badges in game, the USh shop, bounty board,
  playtime pays, build nights as Discord events (works today through event alerts, no code).

## What the bot can see, and why it's split in two parts

The bot runs on `shared-apps`; the Minecraft network runs on `games`, a different VM. Nothing on the tailnet lets
`shared-apps` reach `games`, and `games`' firewall lets nothing in from the house. So today the bot sees the
server exactly as a player does: through `mc.morganvanv.com`.

| | Part 1: from the cheap seats | Part 2: the booth |
|---|---|---|
| Needs | Nothing new. Public data only | A small service in the `games` stack + one tailnet rule (an infra brief) |
| Gives | Linking, `/mc status`, the marquee, the welcome | `/mc shout`, the nudge, Factions postcards, per-mode player counts |

**Public data part 1 uses:** a server-list ping to `mc.morganvanv.com:25565` (the same check Kuma's
`Minecraft public` makes: up/down, players online, version; Velocity's `sample-players-in-ping = false`, so no
names), Mojang's API (Java name → UUID), and GeyserMC's Global API (Bedrock gamertag → XUID → the UUID Floodgate
gives that player in game).

## Part 1: commands (`/mc` group)

| Command | Who | Does |
|---|---|---|
| `/mc register name edition` | anyone | Links a Java or Bedrock account (looked up, so typos are caught and the UUID is stored; names can change, UUIDs don't). Then the join card for that edition and a "where to first?" mode tour. |
| `/mc accounts` | anyone | Your linked accounts; ⭐ default. |
| `/mc whois member` | anyone | Which accounts someone plays (public, never pings). |
| `/mc who name` | anyone | The reverse: which Discord member plays this name. |
| `/mc default name` / `/mc remove name` | anyone | Autocomplete from your accounts. |
| `/mc status` | anyone | Up or down, players online, how to join. |
| `/mc marquee [channel]` | VIP | Posts the marquee there (a status card the VJ keeps up to date, with a "Get me in the game" button). Empty = off. |
| `/mc welcome [channel] [role]` | VIP | When someone gets `role` (the onboarding question's `minecrafter`), the VJ welcomes them once in `channel`, with the same button. Empty channel = off. |

**Onboarding, start to finish:** the onboarding question gives the `minecrafter` role → once they're through the
join gate (`Member.pending` False), the VJ posts one welcome in the minecrafters chat pinging them, with **[Get me
in the game]** → **[I play Java] [I play Bedrock]** → a pop-up asks the name → linked → the join card for their
edition → **where to first?** [Factions] [Anarchy] [Creative] → a short blurb for that mode. The marquee has the same
button, so anyone can start there, and `/mc register` does the same from a command.

Better than the OSRS flow: it starts by itself, it stores UUIDs (OSRS can only store names), and it ends in the
game, not just in Discord. People who already had the role before this shipped aren't welcomed one by one: the
launch announcement is for them.

**Data (additive, two tables + one):**
```sql
mc_accounts (id, discord_id, edition 'java'|'bedrock', uuid UNIQUE, name, is_default, created_at)
mc_settings (guild_id PK, marquee_channel_id, marquee_message_id, welcome_channel_id, welcome_role_id)
mc_welcomed (guild_id, discord_id, PK both)   -- so nobody is welcomed twice
```
**Player names and UUIDs stay out of the logs** (the infra repo's rule for its own logs; the bot's logs are read
by the infra session too). The server's address and ports live in code (`minecraft/server.py`): one network,
same for the dev and prod bots.

## Part 2: the booth (designed, for the infra brief)

A small service, written in Python in this repo (`booth/`, its own image), that runs **inside the `games` stack**
and answers the bot. It's the projection booth: the bot never touches the server's controls directly.

```
bot (shared-apps) ──plain HTTP inside the tailnet, bearer token──► booth (games stack)
                                                                         ├─RCON (stack network)─► factions, anarchy
                                                                         └─reads factions' logs (read-only mount)
```

**What it does (a fixed menu: it never runs a command it was sent):**
- `POST /shout` `{from, text}` → `tellraw @a` on Factions and Anarchy. Text cleaned (≤ 200 characters, no
  control characters or `§` codes), built with `json.dumps` so it can't break out of the message.
- `PUT /linked` `{uuids}` → who's linked (the bot sends it on every change and every 10 minutes).
- The nudge: every 30 s, `list uuids` on each mode; anyone online who isn't linked and wasn't nudged in the last
  day gets one private `tellraw`: "Not in the Discord yet? <invite> · then `/mc register` to link up." Clickable
  on Java; Bedrock shows the text. (Players in the hub can't be reached: PicoLimbo has no console. They get it
  in their first mode.) Text components changed format in 1.21.5 (`click_event`), so it's written for 26.x.
- `GET /status` → players online per mode (better marquee).
- `GET /events?after=N` → **Factions postcards**: joins (the bot turns a UUID's first one into "first time on the
  server"), deaths and advancements, read from Factions' log lines. Chat is never read out or relayed. The bot
  polls and posts them in the postcards channel in the VJ's voice, naming the linked Discord member without
  pinging. A plugin could add EliteMobs boss kills later; logs need nothing installed.

**Why this shape is safe:**
- One direction: the bot calls the booth; `games` never connects to `shared-apps`. One tailnet rule:
  `tag:shared` → `tag:games` on the booth's port only. HTTP inside WireGuard, like Caddy → Geyser today.
- A fixed menu, not a console: a stolen token can shout and nudge, never `op` anyone or stop a server.
- RCON stays on the stack's own network, never published. The booth holds **no Discord secret**: postcards are
  posted by the bot, so a leak on `games` can't post to Discord.
- The container gets the house rules: read-only root, `cap_drop: ALL`, no Docker socket, a read-only mount of
  Factions' `logs/` only, a memory limit.

**What the infra side needs to decide/do (the brief):** the booth's service in `compose.yaml` (image pinned by
digest), **a fixed RCON password** for Factions and Anarchy in the stack's `.env` (`RCON_PASSWORD`; today it's the
image's random one per start), `BOOTH_TOKEN` in both `.env`s (Morgan, at the silent prompt), the tailnet grant
and its tests, the read-only logs mount, a Kuma check if wanted. The bot side gets `BOOTH_URL` and `BOOTH_TOKEN`
(optional: off with a startup warning when missing, contract rule 7).

**`/mc shout message` (part 2, bot side):** anyone; costs **50 USh** to the bank (`ush_ledger` kind `shout`),
VIPs free; a per-person cooldown (5 min) and a global one (30 s) so the game chat isn't flooded. Shown in game as
`[Discord] <display name>: <message>`. The amounts are one constant each, easy to change.

## Discord server checklist (Morgan, by hand)

1. In the `minecrafters` category: **`#mc-status`** (the marquee): everyone View + Read History, no Send; the bot
   (`botmaster12`) View, Send Messages, Embed Links, Read Message History. Then `/mc marquee channel:#mc-status`.
2. `/mc welcome channel:<the category's chat channel> role:@minecrafter`.
3. For part 2: **`#factions-postcards`**, read-only like #mc-status; and a **permanent invite** (never expires,
   no use limit) for the in-game nudge.
4. The launch post in #announcements (draft in the PR), then Publish.
5. Optional: Onboarding's Minecraft answer and the Server Guide can mention `/mc register`.

## Parked
XP for feats in Minecraft and OSRS (Morgan likes it: needs events, so after part 2) · playtime pays · rank badges
in game (LuckPerms) · the USh shop · bounty board · VJ-written server-list text · skin faces on cards (third-party
renderers: terms check first).
