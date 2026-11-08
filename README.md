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
- **/listcommands** (*Lists all available commands in the bot along with their descriptions.*)
- **/ping** (*Checks that the bot is awake: it answers "pong" and the version that's running.*)

### Permissions Cog Commands
- **/checkpermissions** (*Checks the permissions of a user.*)
- **/listbannedusers** (*Lists all banned users.*)
- **/listvipusers** (*Lists all VIP users.*)
- **/grantbanuser [user]** (*Bans a user from using the bot.*)
- **/grantvipuser [user]** (*Grants VIP status to a user.*)
- **/resetpermissions [user]** (*Resets permissions for a user.*)

### Games Cog Commands
- **/coinflip** (*Flips a virtual coin, returning either "Heads" or "Tails."*)
- **/diceroll [sides]** (*Rolls a virtual die with the specified number of sides (default is 6).*)
- **/8ball [question]** (*Answers a yes/no question with a random response, mimicking a Magic 8-Ball.*)
- **/rockpaperscissors [choice]** (*Plays a game of Rock-Paper-Scissors against the bot.*)
- **/threecardmonte** (*Find the winning card among three face-down cards before the dealer packs up.*)

### Fun Cog Commands
- **/say [message]** (*The bot repeats the given message.*)
- **/roast [user]** (*Roasts a user with a random humorous insult.*)
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
- **/gamble [amount]** *(Coming Soon)* (*Gamble your USh.*)

### OSRS Cog Commands
_Link your Old School RuneScape accounts (alts welcome) and flex your drops with the Dink plugin. Design: `docs/osrs-design.md`._
- **/osrs register [rsn]** (*Links an account to your Discord, then asks about flexing, death notifications and the clan.*)
- **/osrs accounts** (*Shows your linked accounts. ⭐ default · 🏰 in the clan.*)
- **/osrs whois [member]** (*Shows which accounts someone plays.*)
- **/osrs default [rsn]** (*Picks your main account.*)
- **/osrs remove [rsn]** (*Unlinks an account.*)
- **/osrs flexing** (*Privately shows what to paste into Dink to post your drops (and, if you want, your deaths).*)
- **/osrs rotate-webhook** (*VIP: replaces a leaked flexing webhook and pings everyone to grab the new one.*)

### Rank Ladder Cog Commands
_Every message is 1 XP and every command 5 (once a minute: more commands within the minute earn nothing), and XP never resets. Your first message makes you **LOWLY SERFS**, then **SWORN SWORDS** (250 XP) and **LORDS** (1,000 XP). Ranks only go up, and you wear one at a time. The bot needs Manage Roles and its role above the three ranks (SETUP_GUIDE step 5)._
- **/ladder show** (*Shows the ranks, how much XP each one needs, and where you are on it.*)
- **/ladder setup [serfs] [swords] [lords] [swords_xp] [lords_xp]** (*VIP: picks the three rank roles and the XP for the upper two.*)
- **/ladder off** (*VIP: stops handing out ranks. Nobody loses a role.*)
- **/ladder tidy** (*VIP: members wearing several ranks keep only their highest, and anyone with less XP than their rank needs is topped up to its minimum. Shows a preview first.*)

### Personal Voice Channels Cog Commands
_Join the lobby voice channel and the VJ makes you your own voice channel and moves you in. It's yours until the last person leaves. Buttons in your channel's chat (only you can use them) set it 🔓 Open, 🔒 Locked (everyone sees it, only guests join) or 👻 Hidden (only guests see it), and ➕ lets in / ➖ removes guests. Your mode and guest list are remembered for next time. The bot needs Manage Channels and Move Members in the personal channels category._
- **/personalvc show** (*Shows the lobby, the staff role, and anything that's stopping it.*)
- **/personalvc setup [hub] [staff]** (*VIP: picks the lobby voice channel and (optionally) the staff role that sees everything.*)
- **/personalvc off** (*VIP: no new personal channels. Open ones stay until they empty; everyone's saved settings are kept.*)

### Music Cog Commands
_Plays from YouTube, SoundCloud, Spotify and Tidal links (tracks, playlists, albums) or a search. The now-playing card has buttons._
- **/play [query] [play_next]** (*Plays a song from a link or search query. Playlists queue every song.*)
- **/join** (*Summons the VJ to your voice channel.*)
- **/leave** (*Sends the VJ home. Clears the queue.*)
- **/pause** / **/resume** (*Intermission, and back.*)
- **/skip** (*Skips the currently playing song.*)
- **/stop** (*Stops the music and clears the queue.*)
- **/queue [page]** (*Shows the current music queue.*)
- **/nowplaying** (*Shows what's playing, with the controls.*)
- **/volume [level]** (*Shows or sets the volume, 0–200%.*)
- **/loop [mode]** (*Loops this song, the whole queue, or nothing.*)
- **/shuffle** (*Shuffles the upcoming songs.*)
- **/remove [position]** (*Removes a song from the queue.*)
- **/effects [effect]** *(Coming Soon)* (*Applies an audio effect to the music.*)

## License

[MIT](LICENSE): fork it, remix it, make your own VJ. Just keep the copyright notice.
