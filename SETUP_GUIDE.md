# Local Setup Guide for VideoJoker on Linux

Welcome to **VideoJoker**! This guide will walk you through getting the bot configured and running locally on your Linux system. 

Since you are transitioning from PyCharm on Windows to **NeoVim** on Linux, use a `.env` file in the project root to manage credentials. The bot's entry point (`main.py`) loads environment variables from this file using `python-dotenv`.

---

## 1. Discord Developer Portal Setup
Before you can run the bot, you need to register it with Discord and obtain credentials.

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications).
2. Click **New Application** in the top right corner and name it (e.g., `VideoJoker`).
3. Set up the Bot:
   - Navigate to the **Bot** tab on the left sidebar.
   - Click **Add Bot** (if not already created).
   - Under the **Token** section, click **Reset Token** and copy the new token. Save this; you will use it as your `DISCORD_TOKEN`.
4. **Enable Privileged Gateway Intents** (CRITICAL):
   - Scroll down to the **Privileged Gateway Intents** section on the same **Bot** tab.
   - Turn **ON** the following intents:
     - **Presence Intent**
     - **Server Members Intent**
     - **Message Content Intent** (required for `intents.message_content = True`)
   - Click **Save Changes**.

---

## 2. Obtain your Discord User ID (for `OWNER`)
The permission manager uses an `OWNER` variable to ensure you always have VIP/admin control.
1. Open your Discord desktop client or web app.
2. Go to **User Settings** (cog icon next to your username) -> **Advanced**.
3. Toggle **Developer Mode** to **ON**.
4. Close settings, right-click on your user profile or avatar, and click **Copy User ID**.

---

## 3. Configuring the Workspace Environment
Since you are using NeoVim, you can manage environment variables cleanly via a `.env` file in the root of your local VideoJoker clone.

Create a `.env` file:
```bash
cd /path/to/VideoJoker
nvim .env
```

Add the following lines, replacing the placeholder values:
```env
DISCORD_TOKEN=your_copied_bot_token_here
OWNER=your_copied_discord_user_id_here
```

*Note: The `.gitignore` file already contains `.env`, ensuring your credentials won't be committed.*

---

## 4. Setting up Docker & Dependencies
Because we are preparing for future music bot capabilities, this project uses Docker to package native system dependencies like `ffmpeg` along with our Python libraries.

1. **Ensure Docker is installed** on your system. You can refer to the [Official Docker Installation Docs](https://docs.docker.com/engine/install/) or install via your package manager:
   - **Arch / Omarchy Linux**:
     ```bash
     sudo pacman -S docker docker-compose
     ```
   - **Debian / Ubuntu**:
     ```bash
     sudo apt update && sudo apt install docker.io docker-compose-v2
     ```
2. **Start the Docker Daemon** (if it isn't running):
   ```bash
   sudo systemctl start docker
   sudo systemctl enable docker
   ```
3. **Add yourself to the docker group** (optional, avoids needing `sudo` for docker commands):
   ```bash
   sudo usermod -aG docker $USER
   ```

---

## 5. Inviting the Bot to your Discord Server
1. Go back to the [Discord Developer Portal](https://discord.com/developers/applications) and select your application.
2. Navigate to the **OAuth2** tab -> **URL Generator**.
3. Under **Scopes**, select:
   - `bot`
   - `applications.commands` (enables slash command registration)
4. Under **Bot Permissions**, select:
   - For a personal test server, **Administrator** is the easiest choice.
   - If you want restricted permissions, select: `Send Messages`, `Embed Links`, `Read Message History`, and `View Channels`.
5. Copy the generated URL at the bottom of the page.
6. Paste the URL into your web browser, select your Discord server, and authorize the bot.

---

## 6. Running the Bot
Once the bot is added to your server and your `.env` is set up, you can start the bot using Docker Compose. The `docker-compose.yml` file is configured to mount your local directory, meaning any changes you make in NeoVim will be synced to the container immediately.

```bash
docker compose up --build
```

### Expected Output:
Upon startup, the console logs should look similar to:
```text
2026-05-29 16:05:00,123 - INFO - Games cog initialized.
2026-05-29 16:05:00,125 - INFO - Fun cog initialized.
2026-05-29 16:05:00,130 - INFO - Utility cog initialized.
2026-05-29 16:05:00,140 - INFO - Permissions cog initialized.
2026-05-29 16:05:01,234 - INFO - Commands synced
2026-05-29 16:05:01,500 - INFO - VideoJoker#1234 has connected.
2026-05-29 16:05:01,501 - INFO - VideoJoker#1234 is now running and ready to serve!
```

Try typing `/ping` in your server—the bot should respond with `pong`.
