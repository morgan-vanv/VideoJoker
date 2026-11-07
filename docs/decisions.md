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
- **2026-10-28** License: MIT (Morgan's call, confirmed after the line above), copyright "Morgan Van Valkenburgh and the VideoJoker contributors" so the crew's work is covered too.
- **2026-10-28** Music is built in pure Python: yt-dlp + ffmpeg inside discord.py, no Lavalink. One more container would be more robust, but the play loop is the part worth learning and owning.
- **2026-10-28** Spotify links resolve to "Artist - Title" and the audio comes from YouTube (Spotify's API doesn't stream). Playlists are read "flat" and each track's stream URL is fetched right before it plays, because stream URLs expire.
- **2026-10-28** Music lives in `music/` (queue/sources/player/ui/lines), same logic-vs-UI split as `games/`. All VJ copy for music is in `music/lines.py`. `cogs/` got an empty `__init__.py` so pylint stops mistaking `cogs/music.py` for the `music` package (same bug existed for `cogs/games.py`).
- **2026-10-28** Music v1 is playback + queue + the now-playing card with buttons. Effects, autoplay, 24/7, radio and DJ roles come as separate PRs (see `docs/music-design.md`).
- **2026-10-28** Trunk-based: no `dev` branch. `main` is always deployable; testing happens in CI and on the dev bot before merging.
- **2026-10-28** Every merge to `main` that changes bot code is a release (date version `vYYYY.MM.DD[.N]`, Docker image on GHCR, auto-generated GitHub Release notes). No release gate, so hotfixes ship as fast as any PR; rollback = previous image tag. `/ping` shows the running version.
- **2026-10-28** Formatter applied now (not after #22) with Morgan's OK while Frankie is away; #22 will need `git merge main` + `ruff format .`. CI checks formatting from here on.
- **2026-10-28** Release images are built with `--provenance=false`: one plain image per tag. Provenance's untagged parts looked like junk and deleting them broke v2026.10.28; flip back if the bot ever goes public.
- **2026-11-06** Production goes live 2026-11-07 on Morgan's server; the host follows GitHub Releases, so every approved merge ships within ~10 min. `main` needs Morgan's approval (CODEOWNERS, #61). The hosting contract lives in `CLAUDE.md` ("Production hosting").
- **2026-11-06** Schema changes are additive only (new tables, or new columns with defaults), because the host's rollback runs the old code against the new database and never restores the copy automatically.
- **2026-11-06** Release workflow also runs monthly (base-image and ffmpeg fixes ship in quiet months) and only ever releases `main` (#62). Heartbeat file `data/heartbeat` every 60 s while connected, so the host can tell connected from running (#63).
- **2026-11-07** Music runs in the read-only prod container: yt-dlp's cache and Deno's (`DENO_DIR`) go in /tmp; the YouTube cookies file must be writable in `data/` (yt-dlp saves it back) or it's skipped with a warning, and lookups take turns while it's in use so it can't be torn.
- **2026-11-07** YouTube playback ships with Deno + yt-dlp-ejs pinned in `requirements.txt` (pip packages, so Dependabot bumps them): yt-dlp needs a JS runtime for YouTube's player challenges, and the JS-less fallback is deprecated. Costs ~100 MB of image.
- **2026-11-07** OSRS linking v1 (`docs/osrs-design.md`): alts first-class, no ownership checks (we trust the server), `/osrs` command group; Wise Old Man's own bot stays for stats/leaderboards. Flexing is "paste-it": the bot owns the Discord webhook (Manage Webhooks), hands it out privately and can rotate it; shared Dink settings live publicly in `osrs/dink-settings.json` (from swannobi's config) with a test that forbids webhook keys, because the old shared webhook leaked from a public config file. No relay for now, so no narrated drops.
- **2026-11-07** OSRS deaths are a per-player opt-in in /osrs register (order: flexing → deaths → clan), posted in their own channel by a "sit, respectfully" webhook; `deathEnabled` left out of the shared Dink settings so the periodic re-import can't switch deaths back on for people who said no.
- **2026-11-07** Music playback: yt-dlp downloads the chosen format and pipes it into ffmpeg (music/stream.py) instead of ffmpeg fetching the link. YouTube signs stream links for the IP + headers that requested them, so ffmpeg's own fetch got 403 in production; this also handles SoundCloud HLS natively. yt-dlp runs in /tmp (its HLS downloader writes chunk files to the current folder, and /app is read-only).
- **2026-11-07** Pin `davey==0.1.7` (Dependabot ignores >=0.2, `tests/test_voice_deps.py` guards it): davey 0.2.0 (2026-11-02) + discord.py 2.7.1 never installs the DAVE encryption key, so the bot plays unencrypted audio into an E2EE call and nobody hears it. Production logged `DAVE protocol 1, encrypting False` with loud frames. Unpin when a discord.py release supports davey 0.2 (Rapptz/discord.py#10549).
