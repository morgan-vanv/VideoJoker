# DISCORD BOT DESIGN DOCUMENT

## Resources & Documentation:

- Intro & Overview of Discord Development: https://discord.com/developers/docs/intro
- discord.py repo: https://github.com/Rapptz/discord.py
- discord.py documentation: https://discordpy.readthedocs.io/en/stable/ext/commands/
- List of Public APIs: https://github.com/public-apis/public-apis
- List of Top Discord Bots: https://top.gg/
  - brainstorm more ideas using this list
- SoundCloud API: https://developers.soundcloud.com/docs/api/guide
- SpotifyAPI: https://developer.spotify.com/

## Examples:

- discord.py Examples: https://github.com/Rapptz/discord.py/tree/master/examples
- Python Music Bot: https://github.com/VenusMods/VenusBot


## Feature Outline:

**Core & Configuration:**
- ✅ ping command (to check if bot is online)
- ✅ sync command (to sync slash commands)
- ✅ listcommands command (list all commands the bot has)
- configuration system
  - we should have a config that is loaded from / saved to, and is user manipulable
  - config should include things like:
    - what channel to use for greetings/farewells
    - what roles can use the bot
    - other settings for other features (raffle settings, reaction role settings, etc.)
- permission system (configurable)
  - role guard the bot commands (only certain roles can use certain commands)
  - probably wouldn't hurt to just stub out role guards for everything even if they are unused

**Utility & Engagement:**
- DM New Members a welcome message with server rules, info, etc. 
- greeting & farewell message upon new member join/leave (ideally in a configurable channel)
- **Reaction Roles**:
  - users reacting to a message will give them a role specific to that message/emoji.
  - ability to link to a prior message and use that to enforce reaction roles.
  - ability to create new messages with reaction roles.
  - option to make the role sticky.
- **XP Leaderboard**:
  - Two specific categories: server engagement and bot engagement.
  - Server engagement: users get 1xp for every message sent.
  - Bot engagement: users get 1xp for every command executed.
- raffle system 
  - randomly selects user of a role, or from a list of users, or from a list of people who react
- reminders (user can set a reminder, bot DMs them when time is up, or sends to a channel)

**Economy System (Currency: UGX - Ugandan Shillings):**
- Users get 1 USh for every message they send.
- Users can send USh between themselves (`pay` command).
- USh can be gambled on games we will add in the future.
- Might be fun with blackjack, robbing, etc.

**Music:**
- Playback controls: play, pause, resume, skip, stop
- Queueing and queue management
- spotify, soundcloud, & youtube links
- radio (lowfi, jazz, etc.) (we could consider real radio stations maybe, but it might be easier to start with streams)
- effects (nightcore, bass boosted, 8d audio, etc.)
- Lyrics fetching

**Games/Fun:**
- ✅ coinflip
- ✅ dice rolling (d20, d6, etc.)
- ✅ 8ball
- ✅ rock paper scissors
- ✅ say, (repeat after me)
- ✅ roast
- tarot readings
- slots
- bacarrat
- blackjack
- russian roulette (solo? or only with multiple people?)
- trivia (general knowledge, or specific categories) (idk this is kinda lame)
- Text to Speech
- translation (input language & message) (google translate api?)
- random bible verse, random quran verse, random bhagavad gita verse

**OSRS:**
- Grand Exchange price lookups (item name or id)

**Longshots (unfeasible/difficult things, but could be cool down the line):**
- listens to the users for voice commands 
  - like "play music", "stop music", "skip song", etc.
  - or just server mute anyone who says "League of Legends"
- a video bot, for streaming videos (from file upload?, youtube, etc.)
  - if we have a `/lyrics` command we could combine with the music bot to do karaoke
- integrations with other bots (like wise old man, etc.)
- integrations with other services (like templeosrs or runeprofile)
- Ai interactions (like chatgpt, dalle, etc.)

**Stupid/funny/junk ideas:**
- job listings in area of your zipcode (https://github.com/public-apis/public-apis?tab=readme-ov-file#jobs)
- random roasts at targeted user
- image recognition (send an image, bot tells you what it is)
- image manipulation (deepfry, memeify, etc.)

