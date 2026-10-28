# Local Setup Guide for VideoJoker

Welcome to **VideoJoker**! This guide will walk you through getting the bot configured and running locally on your system. 

We use a `.env` file in the project root to manage credentials. The bot's entry point (`main.py`) loads environment variables from this file using `python-dotenv`.

---

## 1. Discord Developer Portal Setup
Before you can run the bot, you need to register it with Discord and obtain credentials.

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications).
2. Click **New Application** in the top right corner and name it (e.g., `VideoJoker`).
3. Set up the Bot:
   - Navigate to the **Bot** tab on the left sidebar.
   - Click **Add Bot** (if not already created).
   - Under the **Token** section, click **Reset Token** and copy the new token. Save this; you will use it as your `DISCORD_TOKEN`.
4. **Privileged Gateway Intents: leave them all OFF.**
   - The **Bot** tab lists three privileged intents (Presence, Server Members, Message Content).
     VideoJoker doesn't use any of them: XP and USh only need to know *that* a message was sent, not what it says.
   - If a future feature needs one (e.g. welcome messages need **Server Members**), it gets turned on
     here *and* in `bot.py`, in the same PR.

---

## 2. Obtain your Discord User ID (for `OWNER`)
The permission manager uses an `OWNER` variable to ensure you always have VIP/admin control.
1. Open your Discord desktop client or web app.
2. Go to **User Settings** (cog icon next to your username) -> **Advanced**.
3. Toggle **Developer Mode** to **ON**.
4. Close settings, right-click on your user profile or avatar, and click **Copy User ID**.

---

## 3. Configuring the Workspace Environment
Manage environment variables cleanly via a `.env` file in the root of your local VideoJoker clone.

Copy the template and fill in the two values from steps 1 and 2:

```bash
cp .env.example .env
```

```env
DISCORD_TOKEN=your_copied_bot_token_here
OWNER=your_copied_discord_user_id_here
```

The bot refuses to start without `DISCORD_TOKEN`, and warns you if `OWNER` is missing (then nobody is VIP).

*Note: The `.gitignore` file already contains `.env`, ensuring your credentials won't be committed.*

### Optional: music settings
The music player works out of the box for YouTube and SoundCloud links and searches. These extras are optional:

```env
# Spotify links (track/album/playlist). Create a free app at https://developer.spotify.com/dashboard
# Spotify only gives us the track names; the audio is found on YouTube.
SPOTIFY_CLIENT_ID=...
SPOTIFY_CLIENT_SECRET=...

# Cookies from a logged-in YouTube account (Premium is ideal) avoid YouTube's "confirm you're not a bot" wall.
# Export with a "Get cookies.txt" browser extension and keep the file in data/ (gitignored, mounted in Docker).
YTDLP_COOKIES_FILE=data/cookies.txt

# SoundCloud Go+ token for higher-quality streams (found in the "oauth_token" cookie on soundcloud.com).
SOUNDCLOUD_OAUTH_TOKEN=...
```

---

## 4. Setting up Docker & Dependencies
Because we are preparing for future music bot capabilities, this project uses Docker to package native system dependencies like `ffmpeg` along with our Python libraries.

1. **Ensure Docker is installed** on your system. You can refer to the [Official Docker Installation Docs](https://docs.docker.com/engine/install/).
2. Make sure the Docker daemon is running on your machine.

---

## 5. Inviting the Bot to your Discord Server
1. Go back to the [Discord Developer Portal](https://discord.com/developers/applications) and select your application.
2. Navigate to the **OAuth2** tab -> **URL Generator**.
3. Under **Scopes**, select:
   - `bot`
   - `applications.commands` (enables slash command registration)
4. Under **Bot Permissions**, select only what the bot uses:
   - `View Channels`, `Send Messages`, `Embed Links`, `Read Message History`, `Add Reactions`
   - Later, when those features are built: `Manage Roles` (reaction roles), `Connect` + `Speak` (music).
   - Avoid **Administrator**: it turns any bug into a server-wide one.
5. Copy the generated URL at the bottom of the page.
6. Paste the URL into your web browser, select your Discord server, and authorize the bot.

---

## 6. Running the Bot
Once the bot is added to your server and your `.env` is set up, start it with Docker Compose.
The first time, create the `data/` folder yourself, so it belongs to you rather than to Docker (the bot runs as a normal user and needs to write there):

```bash
mkdir -p data
docker compose up --build -d     # -d = run in the background
docker compose logs -f           # watch the logs (Ctrl+C stops watching, not the bot)
```

The code is built into the image, so **after changing code, run `docker compose up --build -d` again**. Only `data/` (the SQLite database and log files) lives outside the container, so your USh and XP survive rebuilds.

Other everyday commands:

```bash
docker compose stop        # stops the bot cleanly (takes about a second)
docker compose restart     # restart without rebuilding
```

### Expected Output:
Upon startup, the console logs should look similar to:
```text
2026-10-28 16:05:00,101 - root - INFO - Database loaded. VIPs: 1, Banned: 0
2026-10-28 16:05:00,123 - root - INFO - Games cog initialized.
2026-10-28 16:05:00,125 - root - INFO - Fun cog initialized.
...                         (one line per cog)
2026-10-28 16:05:01,234 - root - INFO - Commands synced
2026-10-28 16:05:01,500 - root - INFO - VideoJoker#1234 has connected.
2026-10-28 16:05:01,501 - root - INFO - VideoJoker#1234 is now running and ready to serve!
```

Try typing `/ping` in your server—the bot should respond with `pong`.

---

## 7. A dev bot for testing (recommended)

Test changes on a second, private bot so experiments never touch the real server or the real economy:

1. Repeat step 1 to create a second application (e.g. `VideoJoker Dev`), and invite it to a private test server (step 5).
2. `cp .env.example .env.dev` and fill in the **dev** bot's token, your `OWNER`, and `DEV_GUILD_ID`
   (with Developer Mode on, right-click your test server → **Copy Server ID**). Commands then appear instantly, in that server only.
3. `mkdir -p data-dev`, then `docker compose -f compose.dev.yml up --build`

The dev bot uses its own `data-dev/` database and mounts your working folder, so after editing code just run
`docker compose -f compose.dev.yml restart`. Never put the real bot's token in `.env.dev`.

---

## 8. Working on the code

```bash
python3 -m venv .venv && source .venv/bin/activate    # Python 3.14, see .python-version
pip install -r requirements-dev.txt
pylint --rcfile=.pylintrc $(git ls-files '*.py')       # CI fails below 9.5 or on any error
python -m pytest                                       # quick tests, no Discord needed
```

CI runs the same checks on every pull request. Work on a branch, open a PR, and a human merges it.

---

## 9. Backups and troubleshooting

- **Back up the database** now and then (everyone's USh and XP live in this one file):
  ```bash
  docker compose stop && cp data/videojoker.db ~/videojoker-backup-$(date +%F).db && docker compose start
  ```
- **`PermissionError` on `data/`** (e.g. after upgrading from an older setup that ran as root):
  `sudo chown -R "$(id -u):$(id -g)" data`. If `id -u` isn't 1000, build with `docker compose build --build-arg UID=$(id -u)`.
- **Commands not showing up?** Global commands can take a little while to appear after a change. Restarting Discord (Ctrl+R) helps.

