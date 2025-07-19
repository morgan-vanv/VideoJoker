# DISCORD BOT DESIGN DOCUMENT

## Resources & Documentation:

- Intro & Overview of Discord Development: https://discord.com/developers/docs/intro
- discord.py repo: https://github.com/Rapptz/discord.py
- discord.py documentation: https://discordpy.readthedocs.io/en/stable/ext/commands/
- List of Public APIs: https://github.com/public-apis/public-apis
- List of Top Discord Bots: https://top.gg/
  - brainstorm more ideas using this list

## Examples:

- discord.py Examples: https://github.com/Rapptz/discord.py/tree/master/examples
- Python Music Bot: https://github.com/VenusMods/VenusBot


## Feature Outline:

**Core:**
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
  - should we role guard every command? or just admin commands?
  - probably wouldn't hurt to just stub out role guards for everything even if they are unused

**Utility:**
- DM New Members a welcome message with server rules, info, etc. 
- greeting & farewell message upon new member join/leave (ideally in a configurable channel)
- reaction roles (react to this message to gain a role, have option to make the role sticky)
  - iron out how we want this to work specifically: 
  - *do we want the bot to create an embed, or have the user provide a message id? do we want to support multiple messages? etc.*
- raffle system 
  - randomly selects user of a role, or from a list of users, or from a list of people who react
- role guard the bot commands (only certain roles can use certain commands)

**Music:**
- spotify, soundcloud, & youtube links
- radio (lowfi, jazz, etc.) (we could consider real radio stations maybe, but it might be easier to start with streams)
- effects (nightcore, bass boosted, 8d audio, etc.)
- queueing, queue management, skipping

**Games/Fun:**
- ✅ coinflip
- ✅ dice rolling (d20, d6, etc.)
- ✅ 8ball
- ✅ rock paper scissors
- tarot readings
- slots
- bacarrat
- blackjack
- russian roulette (solo? or only with multiple people?)
- trivia (general knowledge, or specific categories) (idk this is kinda lame)

**Fun:**
- ✅ say, (repeat after me)
- ✅ roast
- Text to Speech
- translation (input language & message) (google translate api?)
- random bible verse, random quran verse, random bhagavad gita verse

**OSRS:**
- Grand Exchange price lookups (item name or id)


**Longshots (unfeasable/difficult things, but could be cool down the line):**
- currency system? idk if people would use that (might be fun with blackjack, robbing, etc.)
- a video bot, for streaming videos (from file upload?, youtube, etc.)
- integrations with other bots (like wise old man, etc.)
- integrations with other services (like templeosrs or runeprofile)
- Ai interactions (like chatgpt, dalle, etc.)

**stupid/funny/junk ideas**
- job listings in area of your zipcode (https://github.com/public-apis/public-apis?tab=readme-ov-file#jobs)
- random roasts at targeted user
- image recognition (send an image, bot tells you what it is)
- image manipulation (deepfry, memeify, etc.)

