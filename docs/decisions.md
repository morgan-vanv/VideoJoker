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
- **2026-10-28** Ran a foundation audit before new features; fixes land as small, independent PRs in impact order (security → CI/tests → deployment → code quality → docs → hygiene), humans merge each one.
- **2026-10-28** Adopt `ruff format` only (quotes preserved, line length 120) as one final repo-wide commit listed in `.git-blame-ignore-revs`, after #22 lands and with Frankie's OK; pylint stays the linter. Ends style debates without hiding who wrote what.
- **2026-10-28** Standardize on Python 3.14 everywhere (Docker, CI, `.pylintrc`, `.python-version`): it's what Morgan develops on, and 3.11 loses security fixes in Oct 2027.
- **2026-10-28** CI lints the whole repo (it's small, and the changed-files trick silently linted nothing), with `fixme` disabled for the intentional stub TODOs and a `--fail-under=9.5` score gate.
- **2026-10-28** Keep the flat VIP model (any VIP can grant/ban, only the owner is protected) on purpose: the crew trusts each other. Revisit if the bot joins servers beyond the friend group.
- **2026-10-28** Use `discord.Intents.default()`: no privileged intent is used today. Turn Members back on when someone builds welcome messages.
- **2026-10-28** Leave `/say` and passive income without cooldowns for now: rate limits are game-design calls for whoever builds `/gamble`.
- **2026-10-28** Dev tools live in `requirements-dev.txt`, not the image; unused `requests`/`aiofiles` removed; `yt-dlp` kept (bumped) for the music stub. PyNaCl stays at 1.5.0 because discord.py 2.7.1 requires <1.6 (its advisory doesn't affect voice encryption).
- **2026-10-28** Default `docker compose` runs the code baked into the image with only `./data` mounted; a `compose.dev.yml` override adds the live source mount. No HEALTHCHECK: a bot has no port to probe and discord.py reconnects itself.
- **2026-10-28** Remove the unused `restart_bot()`; `docker compose restart` does that job.
- **2026-10-28** Protect `main`: PRs and a passing lint check required, no force-push or deletion, no required approvals (two people; approvals would stall).
- **2026-10-28** Merged branches are archived as `archive/<name>` tags, then deleted; GitHub auto-deletes head branches from now on.
- **2026-10-28** MIT license proposed, pending Frankie's agreement since it covers his code too. README will credit the crew in Morgan's words.
