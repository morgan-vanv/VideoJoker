# Decision log

One line per decision, newest at the bottom, with the reason. Entries before 2026-10-27 were
reconstructed from git history — correct anything that's off.

- **2025-07-18** Project started as a discord.py bot paying homage to the Ugandan Video Joker tradition.
- **2025-07-26** Moved to slash commands (`app_commands`) with typed `discord.Interaction` handlers; added VIP/BANNED permissions with a global banned-user check and a global error handler.
- **2025-07-26** Added a Pylint GitHub Action on `dev`/`main`, linting only changed files.
- **2026-05-30** Revived the project: flattened the layout into `cogs/` + `core/`, and moved permissions into SQLite (aiosqlite) with an in-memory cache.
- **2026-05-30** Dockerized (ffmpeg/libopus included) so friends can run the bot the same way and music is possible later.
- **2026-06-01** Stubbed out economy, music, reaction roles and leaderboard on purpose, as starter work for collaborative development.
- **2026-06-06** Friends' features are improved through "remux" branches the original author reviews, rather than rewritten in place (Three Card Monte).
- **2026-06-07** Multi-file games live under `games/<name>/` with `engine.py` (logic) separate from `ui.py` (discord Views).
- **2026-10-27** Added `CLAUDE.md` so AI help follows the house rules: branches + PRs, ask before changing friends' code, keep the voice, label AI work.
