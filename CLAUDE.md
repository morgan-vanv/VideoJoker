# CLAUDE.md — working on VideoJoker

VideoJoker is a Discord bot built by Morgan and friends as a hands-on way to learn collaborative
development. It's an homage to the Ugandan Video Joker tradition (see README). The code is small,
handcrafted, and sentimental. **Treat it like a friend's workshop, not a codebase to optimize.**

## Hard rules

1. **Never commit to `main` directly.** Work on a branch (`feature/…`, `fix/…`, `chore/…`), open a PR,
   and let a human merge it. Never force-push, rebase, or rewrite shared history.
2. **Don't rewrite other people's code without asking.** If you want to change something a friend
   wrote, say so first. If the change is welcome, do it the house way: a *remux* — a separate
   branch/PR the original author can review (see `feature/frankiecardmonte_morganremux` for the
   precedent). Credit them with a `Co-authored-by:` trailer when you build on their work.
3. **Keep `git blame` meaningful.** No repo-wide reformatting, import re-sorting, or "while I'm here"
   cleanups in files you weren't asked to touch. Small, focused diffs only.
4. **Don't sand off the voice.** Roasts, "comrade", the dealer packing up his cards, the USh economy,
   the VJ flavor — that's the point of the bot. Inside jokes stay. Don't "professionalize" copy.
5. **Don't eat the stubs.** Stubbed commands (music, reaction roles, leaderboard, gamble) may be
   things a friend wants to build. Ask before implementing one.
6. **Label AI work.** This repo has a tradition of flagging AI-generated changes ("AI GENERATED!!
   BEWARE!"). Keep the co-author trailer on commits and say plainly in the PR what was AI-written.
7. **Never commit secrets.** Credentials live in `.env` (gitignored). `data/` (SQLite DB, logs) is
   runtime state and is never committed.

## Stack

- Python 3.14 (Docker image `python:3.14.10-slim-trixie`; `.python-version` for CI and local tools), discord.py 2.7 (slash commands via `app_commands`),
  aiosqlite, python-dotenv. ffmpeg/libopus are installed for future music work.
- Entry point `main.py` → `bot.py` (`VideoJoker(commands.Bot)`), which loads cogs in `setup_hook`.

## Layout

| Path | What lives there |
|---|---|
| `main.py` | Creates `data/` dirs, logging, loads `.env`, starts the bot |
| `bot.py` | Bot class, global error handler, banned-user check, `/ping`, `/listcommands` |
| `cogs/` | One cog per feature area; each ends with `async def setup(bot)` |
| `core/database.py` | Single aiosqlite connection + in-memory VIP/BANNED cache; all SQL lives here |
| `core/constants.py` | Static content (8-ball answers, RPS rules, roasts) |
| `core/custom_exceptions.py` | `app_commands.CheckFailure` subclasses for permissions |
| `games/<game>/` | Multi-file games: `engine.py` (pure logic) + `ui.py` (discord Views) |

## Conventions

- New command → add it to the matching cog; new cog → also add it to `initial_extensions` in `bot.py`.
- Bigger games get a package under `games/` with logic separated from UI.
- Permission checks use the `is_vip()` decorator in `cogs/permissions.py`; banned users are blocked
  globally in `bot.global_interaction_check`.
- Use `logging` with `%s` args, not f-strings. Max line length 120 (`.pylintrc`).
- When you add or rename a command, update the README's command list in the same PR.
- `main` is always deployable: merging a PR that changes bot code creates a release automatically (`.github/workflows/release.yml`). There is no `dev` branch.

## Production hosting (live since 2026-11-07)

Every approved merge to `main` that changes the bot is live on Morgan's server within ~10 minutes: the host
watches for new GitHub Releases, switches over, and rolls back on its own if the bot doesn't come up. So
these rules hold for every PR. If a change has to break one, say so in the PR:

1. The log line `… is now running and ready to serve!` (`bot.py` `on_ready`) stays word for word: the host's start check looks for it.
2. SIGINT shuts down cleanly and closes the database within a few seconds.
3. The container runs as UID 1000 with a **read-only** filesystem. The only writable places are `/app/data`
   (database, logs, heartbeat) and `/tmp` (256 MB). Downloads and caches (yt-dlp included) must go there.
4. Schema changes must be **forward-compatible**, because a rollback runs the *old* code against the *new*
   database: add tables, or add columns with a default. Never rename, drop, or change what a column means.
5. `Intents.default()` only. The production bot is invited with View Channels, Send Messages, Embed Links
   and Read Message History. A feature that needs more (e.g. `Connect`/`Speak` for music, `Manage Roles`
   for reaction roles) or a privileged intent must say so in its PR, so Morgan can re-invite the bot.
6. Production has no `DEV_GUILD_ID` (commands sync globally). The dev bot stays in the test server.

## Checks before opening a PR

```bash
pip install -r requirements-dev.txt                 # bot deps + dev tools (pylint)
ruff format .                                        # format first: CI fails if anything isn't formatted
pylint --rcfile=.pylintrc $(git ls-files '*.py')     # CI runs exactly this on the whole repo: fails below 9.5 or on any error
python -c "import bot, cogs.games, cogs.fun, cogs.utility, cogs.permissions, cogs.music, cogs.economy, cogs.reaction_roles"
python -m pytest                                     # tests in tests/: database + game logic, no Discord needed
```

Tests can't cover anything that needs Discord itself. Running the bot for real needs a token
(`docker compose up --build`), so say in the PR when a change still needs a manual test in Discord.
When you change `core/database.py` or game logic, add or update a test in `tests/`.

## Decisions

Record design decisions in `docs/decisions.md` (one dated line each, with the why).
