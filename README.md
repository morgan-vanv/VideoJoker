# VideoJoker

## Overview
VideoJoker is a Discord bot, inspired by and stylized after the Video Joker character from the Wakaliwood film *"Who Killed Captain Alex?"*. 
This is for my own personal use, but feel free to fork and modify it for your own needs.

## Getting Started
To configure and run the bot locally using Docker, follow the step-by-step instructions in the [SETUP_GUIDE.md](SETUP_GUIDE.md).


---

**What is a Video Joker?**

A Video Joker (VJ) is essentially a commentator who narrates and dubs over movies — originally foreign ones — in Uganda. 
This tradition began in the 1980s and 1990s when access to foreign films was mostly through bootleg VHS tapes. 
Most of these films were in English, Hindi, or Chinese, languages not understood by the majority of Ugandans. 
So the Video Joker would:

- Translate dialogue (not always literally, often adding their own flair).

- Offer context, jokes, and reactions to on-screen events.

- Often inject themselves as part of the film experience with catchphrases and recurring gags.

Even to this day, Video Jokers remain popular in Uganda, especially for action and martial arts films. 
We also see similar practices in other countries. I've always found this to be one of my favorite parts of films that have them.

**So then, what is this?**

Mostly a fun side project to learn more about Discord bots and to pay homage to the VJ tradition. 
Maybe one day this will be available to the public rather than just open source, but for now it's just for me to mess around with.
I don't even know why I spent so long on this README lol

----

## Implemented Features
_See `DESIGNDOCUMENT.md` for information on what might come in the future_

### Main Bot Commands
- **/help** (*New here? A quick tour of what the bot does on this server: XP and ranks, USh, the leaderboard, music, your own voice channel, games, OSRS and Minecraft. Only you see it, and features this server hasn't set up are left out.*)
- **/listcommands** (*Lists the commands in the bot along with their descriptions, subcommands included (`/ladder show`, `/osrs register`, ...). VIP-only commands are left out.*)
- **/listadmincommands** (*VIP: lists the VIP-only commands that `/listcommands` leaves out. Only you see it.*)
- **@VideoJoker ping** (*Admins: type it as a message, mentioning the bot. It answers "pong" and the version that's running. It's not a slash command, so it stays out of the `/` menu.*)

### Setup (VIPs only, hidden from everyone else's `/` menu)
_Everything you set up once per server lives under `/setup`. Discord shows it only to people who can Manage Server; the owner can show it to another role in Server Settings → Integrations → VideoJoker. Every subcommand is VIP-only too._
- **/setup show** (*Everything set up in this server, with ⚠️ on anything that stops a feature working. Only you see it.*)
- **/setup ladder set [serfs] [swords] [lords] [swords_xp] [lords_xp]** (*Picks the three rank roles and the XP for the upper two.*)
- **/setup ladder off** (*Stops handing out ranks. Nobody loses a role.*)
- **/setup ladder tidy** (*Members wearing several ranks keep only their highest, and anyone with less XP than their rank needs is topped up to its minimum. Shows a preview first.*)
- **/setup voice set [hub] [staff]** (*Picks the personal-channel lobby and (optionally) the staff role that sees everything.*)
- **/setup voice off** (*No new personal channels. Open ones stay until they empty; everyone's saved settings are kept.*)
- **/setup events [channel]** (*The channel for this server's event reminders. Leave it empty to switch them off.*)
- **/setup minecraft marquee [channel]** (*Keeps a Minecraft status card in a channel, updated every couple of minutes. Empty = off.*)
- **/setup minecraft welcome [channel] [role]** (*Welcomes people once when they get the Minecraft role from onboarding. Empty = off.*)
- **/setup minecraft postcards [channel]** (*Posts postcards from the server: first-timers on the network, deaths and advancements on Factions. Empty = off. Needs the booth.*)
- **/setup osrs-webhook** (*Replaces a leaked OSRS flexing webhook and pings everyone to grab the new one.*)
- **/setup people vip | ban | reset [user]** (*Gives VIP, bans someone from the bot, or takes either away.*)
- **/setup people check [user]** / **vips** / **banned** (*Is someone a VIP or banned; everyone with VIP; everyone banned.*)

### Games Cog Commands
- **/coinflip** (*Flips a virtual coin, returning either "Heads" or "Tails."*)
- **/roll [sides] [dice]** (*Rolls dice: one six-sided die by default, or up to 10 dice of up to 100 sides. Frankie's `/droll` and `/diceroll` in one.*)
- **/8ball [question]** (*Answers a yes/no question with a random response, mimicking a Magic 8-Ball.*)
- **/rockpaperscissors [choice]** (*Plays a game of Rock-Paper-Scissors against the bot.*)
- **/threecardmonte** (*Find the winning card among three face-down cards before the dealer packs up.*)

### Fun Cog Commands
- **/say [message]** (*The bot repeats the given message.*)
- **/curseofra [user]** (*shut up, bozo. Curses a user with a fresh wall of hieroglyphs (the Curse of Ra meme). Pings them.*)
- **/russianroulette** (*Russian Roulette simulator.*)

### Utility Cog Commands
- **/userinfo [user]** (*Displays information about a user, including their nickname, ID, and the date they joined Discord.*)
- **/serverinfo** (*Displays information about the server, including its name, ID, member count, and creation date.*)
- **/rank [user]** (*Your or another member's rank, XP, how far the next rank is, place on the server, and USh. Never pings.*)
- **/leaderboard** (*The server's top 10 for XP, with a button to switch to USh. Your own place shows too, even outside the top 10.*)

### Economy Cog Commands
_USh (Ugandan shillings) is the VJ's play money: every message earns 1. Payments are kept in a ledger, so `/balance` can show the latest ones._
- **/balance [user]** (*Your or another member's USh and their last 5 payments. Never pings.*)
- **/pay [user] [amount] [note]** (*Sends USh to another member, with an optional note (up to 100 characters). Pings only the person you paid.*)

### OSRS Cog Commands
_Link your Old School RuneScape accounts (alts welcome) and flex your drops with the Dink plugin. Design: `docs/osrs-design.md`._
- **/osrs register [rsn]** (*Links an account to your Discord, then asks about flexing, death notifications and the clan.*)
- **/osrs accounts** (*Shows your linked accounts. ⭐ default · 🏰 in the clan.*)
- **/osrs whois [member]** (*Shows which accounts someone plays.*)
- **/osrs default [rsn]** (*Picks your main account.*)
- **/osrs remove [rsn]** (*Unlinks an account.*)
- **/osrs flexing** (*Privately shows what to paste into Dink to post your drops (and, if you want, your deaths).*)

### Minecraft Cog Commands
_Link your Java or Bedrock account, see who plays what, and check on the server at `mc.morganvanv.com`. Design: `docs/minecraft-design.md`._
- **/mc register [name] [edition]** (*Links a Java or Bedrock account (looked up, so typos are caught), then shows how to join and the modes.*)
- **/mc accounts** (*Shows your linked accounts. ⭐ default.*)
- **/mc whois [member]** (*Shows which accounts someone plays.*)
- **/mc who [name]** (*Shows which member plays a Minecraft name.*)
- **/mc default [account]** (*Picks your main account.*)
- **/mc remove [account]** (*Unlinks an account.*)
- **/mc status** (*Is the server up, and how many are on (per mode, once the booth is wired up)? With a "Get me in the game" button.*)
- **/mc shout [message]** (*Shouts into every awake mode's chat as `[Discord] You: message`. 50 USh to the bank (VIPs free); once every 5 minutes each, once every 30 seconds for everyone. Nobody awake to hear it = no charge. Needs the booth.*)

### Rank Ladder Cog Commands
_Every message is 1 XP and every command 5 (once a minute: more commands within the minute earn nothing), and XP never resets. Your first message makes you **LOWLY SERFS**, then **SWORN SWORDS** (250 XP) and **LORDS** (1,000 XP). Ranks only go up, and you wear one at a time. When you climb, your next slash command in that server comes with a private note (only you see it) about your new rank and what it unlocks. The bot needs Manage Roles and its role above the three ranks (SETUP_GUIDE step 5)._
- **/ladder show** (*Shows the ranks, how much XP each one needs, and where you are on it.*)

### Personal Voice Channels Cog Commands
_Join the lobby voice channel and the VJ makes you your own voice channel and moves you in. It's yours until the last person leaves. Buttons in your channel's chat (only you can use them) set it 🔓 Open, 🔒 Locked (everyone sees it, only guests join) or 👻 Hidden (only guests see it), and ➕ lets in / ➖ removes guests. Your mode and guest list are remembered for next time. The bot needs Manage Channels and Move Members in the personal channels category. A VIP switches it on with `/setup voice set`._

### Event Alerts Cog Commands
_Discord's own events (Events, top of the channel list) do the scheduling, weekly repeats and "Interested". The VJ adds a heads-up before each event (the day before and an hour before) pinging everyone marked Interested, and posts when an event's time or place changes or it's cancelled. No commands for any of that: it follows the events. The bot needs Send Messages and Embed Links in the alert channel. Reminder times: `EVENT_ALERT_TIMES` in `.env`. A VIP picks the channel with `/setup events`._

### Raffle Cog Commands
_Put up a prize, people react 🎟️ on the raffle card to enter, and the winner is drawn when time's up (it survives restarts). Bots, banned users and the host can't win. One running raffle per person per server._
- **/raffle start [prize] [duration] [winners]** (*Starts a raffle in this channel. Duration like `30m`, `2h` or `1d 12h` (1 minute to 7 days); 1 to 5 winners.*)
- **/raffle cancel [raffle]** (*Calls off a raffle without drawing a winner. Your own, or anyone's for VIPs.*)
- **/raffle end [raffle]** (*Draws the winner now instead of waiting. Your own, or anyone's for VIPs.*)

### Music Cog Commands
_Plays from YouTube, SoundCloud, Spotify and Tidal links (tracks, playlists, albums) or a search. Pause/resume, skip, stop, shuffle, loop and the queue are buttons on the now-playing card._
- **/play [query] [play_next]** (*Plays a song from a link or search query, joining your voice channel. Playlists queue every song.*)
- **/skip** (*Skips the currently playing song.*)
- **/queue [page] [remove]** (*Shows what's coming up; `remove` takes out the song with that number.*)
- **/nowplaying** (*Shows what's playing and moves the card with the buttons here.*)
- **/volume [level]** (*Shows or sets the volume, 0–200%.*)
- **/leave** (*Sends the VJ home. Clears the queue.*)

_Stubs kept out of the `/` menu until someone builds them: `/gamble` (`cogs/economy.py`) and `/effects` (`cogs/music.py`)._

## License

[MIT](LICENSE): fork it, remix it, make your own VJ. Just keep the copyright notice.
