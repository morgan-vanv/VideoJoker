# The booth

A small Python service that runs **next to the Minecraft servers** and does a fixed list of things for VideoJoker:
`/mc shout`, the in-game "join our Discord" nudge, players per mode, and postcards. Why it exists and how it fits:
`docs/minecraft-design.md`, "Part 2". It never imports the bot; it ships as its own image.

## The image

`ghcr.io/morgan-vanv/videojoker-booth:<version>` (and `:latest`), built by the same release as the bot, with the
same date version. Pin it by digest. Python 3.14 slim, aiohttp only, runs as UID 1000, **writes nothing to disk**
(fine with a read-only root and no writable volume), listens on one port.

## Settings (environment)

| Name | Needed | What |
|---|---|---|
| `BOOTH_TOKEN` | yes | Shared secret with the bot, at least 32 characters (`openssl rand -hex 32`). The bot sends it as `Authorization: Bearer …`. |
| `RCON_PASSWORD` | yes | The RCON password of every mode listed in `BOOTH_MODES` (one password for all). |
| `BOOTH_MODES` | yes | Which modes to talk to, as `name=host:port`, comma-separated, e.g. `factions=factions:25575,anarchy=anarchy:25575`. A new mode is a new entry, no new image. |
| `BOOTH_INVITE` | no | A permanent Discord invite link for the nudge. Without it, no nudge. |
| `BOOTH_FACTIONS_MODE` | no | Which `BOOTH_MODES` name is Factions (default `factions`). |
| `BOOTH_VELOCITY_LOG` | no | Velocity's log file (default `/logs/velocity/latest.log`). |
| `BOOTH_FACTIONS_LOG` | no | Factions' log file (default `/logs/factions/latest.log`). |
| `BOOTH_NUDGE_HOURS` | no | How long before the same player is nudged again (default `24`). |
| `BOOTH_PORT` | no | Port to listen on (default `8765`). |

A missing required setting stops it at start with a clear message (better than half working).

## Mounts

Two **read-only** mounts of log folders, nothing else: Velocity's `logs/` at `/logs/velocity` and Factions'
`logs/` at `/logs/factions`. A missing file (a mode asleep, or not started yet) is waited for, not an error. When a
server starts a fresh `latest.log`, the booth notices and follows the new one.

## Network

- **In:** only the bot, over the tailnet, on `BOOTH_PORT`. Plain HTTP inside WireGuard. Every route but `/health`
  needs the token.
- **Out:** RCON to each mode in `BOOTH_MODES` on the stack's own network. Nothing to the internet, and no Discord
  secret: postcards are posted by the bot, which polls `/events`.

## The menu (all it can do)

| Route | Does |
|---|---|
| `GET /health` | `ok` (no token; for Kuma). |
| `GET /status` | `{"modes": {"factions": {"awake": true, "online": 3}, "anarchy": {"awake": false, "online": 0}}}` |
| `POST /shout` `{"from", "text"}` | `tellraw @a` in every awake mode: `[Discord] Name: text`. Answers `{"heard": [...], "asleep": [...]}`. |
| `PUT /linked` `{"uuids": [...]}` | Who has linked an account. Until the bot sends this once, nobody is nudged. |
| `GET /events?after=N` | `{"boot", "latest", "events": [{"id", "kind": "join"\|"death"\|"advancement", "name", "text"?, "title"?}]}` |

On its own, every 30 seconds it runs `list uuids` in each awake mode and sends one private `tellraw` to each
unlinked player it hasn't nudged in `BOOTH_NUDGE_HOURS`. It reads Velocity's log for joins (whole network) and
Factions' log for deaths and advancements. Nothing from Anarchy's log, ever.

There is **no "run this command"** route. Text that ends up in game is cleaned (no control characters, no `§`, at
most 200 characters) and built with `json.dumps`, so it can't break out of the message.

## Sleeping modes

A mode whose RCON doesn't answer is asleep: shouts and nudges skip it quietly, `/status` reports it as asleep.
A wrong RCON password is logged once per mode, as an error.

## Privacy

- **Player IPs:** Velocity's "has connected" line holds the player's IP. The booth takes the name and drops the
  rest of the line on the spot: IPs are never kept, logged or sent.
- **Player names** never go into the booth's own log (counts and mode names only). Postcards carry names to the
  bot, which is what they're for. Chat is never read out.
- Everything is in memory: a restart forgets who was nudged (they may get one more nudge) and the postcard queue
  (the bot sees the new `boot` and carries on).

## Try it locally

```bash
docker build -f booth/Dockerfile -t videojoker-booth .
docker run --rm -e BOOTH_TOKEN=$(openssl rand -hex 32) -e RCON_PASSWORD=pw \
  -e BOOTH_MODES=factions=host.docker.internal:25575 -p 8765:8765 videojoker-booth
curl localhost:8765/health
```
Tests: `python -m pytest tests/test_booth.py tests/test_minecraft_booth.py` (a fake RCON console, fake logs, and
the bot's own client against the real app).
