"""Everything the VJ says for the Minecraft features, in one place. Edit freely: it's just text.

{curly} bits are filled in by the code with .format(...). The address and ports come from minecraft/server.py.
"""

from minecraft.server import ADDRESS, BEDROCK_PORT, MODES

MODE_NAMES = dict(MODES)  # "factions" → "Factions"; a mode the bot doesn't know yet shows as its own name

EDITION_NAMES = {"java": "Java", "bedrock": "Bedrock"}
SERVICES = {"java": "Mojang", "bedrock": "Xbox (through GeyserMC)"}

# ---- getting started (the welcome, the marquee and /mc status all have this button)
START_BUTTON = "Get me in the game"
EDITION_QUESTION = "🎮 Which Minecraft do you play?"
JAVA_BUTTON = "Java (PC)"
BEDROCK_BUTTON = "Bedrock (phone, console, Windows)"
MODAL_TITLE = "Your Minecraft name"
MODAL_LABELS = {"java": "Your Java username", "bedrock": "Your Xbox gamertag"}

# ---- /mc register
INVALID_NAME = {
    "java": "🚫 **{name}** can't be a Java name. They're up to 16 letters, numbers or `_`, no spaces.",
    "bedrock": "🚫 **{name}** can't be a gamertag. They're up to 16 letters, numbers or spaces.",
}
NOT_FOUND = {
    "java": "🔎 Mojang has never heard of **{name}**. Check the spelling, comrade.",
    "bedrock": "🔎 Xbox has no gamertag called **{name}**. Check the spelling (spaces count).",
}
LOOKUP_DOWN = "📡 The VJ can't reach {service} right now to check that name. Try again in a few minutes."
LINKED = "✅ **{name}** ({edition}) is now linked to you."
LINKED_DEFAULT = " It's your default."
ALREADY_YOURS = "👍 **{name}** ({edition}) was already yours. Welcome back to the screening."
TAKEN = "🚫 **{name}** ({edition}) is already linked to {owner}. If that's wrong, ask them to `/mc remove` it."

# ---- the join card, then "where to first?"
JOIN = {
    "java": (
        f"## 🎬 How to get in (Java)\n"
        f"**Multiplayer → Add Server**, address `{ADDRESS}`. No port needed.\n"
        f"You land in the hub: pick a mode from the chat menu, or type `/server factions`."
    ),
    "bedrock": (
        f"## 🎬 How to get in (Bedrock)\n"
        f"**Play → Servers → Add Server**, address `{ADDRESS}`, port `{BEDROCK_PORT}`.\n"
        f"You land in the hub: a menu pops up to pick a mode (or type `/server factions`)."
    ),
}
WHERE_FIRST = "🗺️ Where to first?"
MODES = {
    "factions": (
        "⚔️ **Factions**: the forever world, back from the old factions server, kingdoms and homes included. "
        "Claim land with your crew, raid EliteMobs dungeons, level your skills. In game: `/server factions`."
    ),
    "anarchy": (
        "💀 **Anarchy**: pure vanilla, hard mode, no rules, no claims. Backed up against disk failure, never against "
        "your friends: nothing gets rolled back. In game: `/server anarchy`."
    ),
    "creative": (
        "🎨 **Creative**: a plot of your own to build on. The projector's still warming up (it's waiting on its "
        "plots plugin): the VJ will shout when it opens. Until then, Factions or Anarchy?"
    ),
}

# ---- /mc accounts, /mc whois, /mc who, /mc default, /mc remove
NO_ACCOUNTS = "You haven't linked a Minecraft account yet. Start with `/mc register`."
NOT_YOURS = "🚫 **{name}** isn't one of your linked accounts. `/mc accounts` shows what is."
NEW_DEFAULT = "⭐ **{name}** is now your default."
REMOVED = "🗑️ **{name}** is no longer linked to you."
ACCOUNTS_TITLE = "{member}'s Minecraft accounts"
ACCOUNTS_LEGEND = "⭐ default"
WHOIS_NOBODY = "{member} hasn't linked a Minecraft account."
WHO_NOBODY = "🔎 Nobody here has linked **{name}**."
WHO_FOUND = "🎭 **{name}** ({edition}) is {member}."

# ---- /mc status and the marquee
STATUS_TITLE = f"🎬 Now showing: {ADDRESS}"
STATUS_UP = "🟢 **Showing now.** {online}/{max} in the dark."
STATUS_UP_EMPTY = "🟢 **Showing now.** The seats are empty: be the first in."
STATUS_DOWN = "🔴 **Intermission.** The server isn't answering. The VJ is checking the reels."
STATUS_HOW = (
    f"**Java:** Multiplayer → Add Server → `{ADDRESS}`\n"
    f"**Bedrock:** Servers → Add Server → `{ADDRESS}`, port `{BEDROCK_PORT}`"
)
STATUS_HOW_NAME = "How to get in"
STATUS_MODES_NAME = "On the screen"
STATUS_MODES = "⚔️ Factions · 💀 Anarchy · 🎨 Creative (soon)"
STATUS_FOOTER = "Link your account: /mc register · Checked"

# ---- the welcome (when someone gets the Minecraft role)
WELCOME = (
    "🎬 {member}, the Minecraft screen is back on! `{address}`, Java and Bedrock in one world. "
    "Hit the button and the VJ walks you in."
)

# ---- /mc marquee and /mc welcome (VIP)
MARQUEE_ON = "🎬 The marquee is up in {channel}. The VJ checks the server every couple of minutes."
MARQUEE_OFF = "🎬 Marquee off. The old card stays where it is until someone deletes it."
WELCOME_ON = "🎬 Anyone who gets {role} is welcomed once in {channel}."
WELCOME_OFF = "🎬 Minecraft welcomes off."
WELCOME_NEEDS_ROLE = "🚫 Tell the VJ which role to watch for (the onboarding question's Minecraft role)."
NO_PERMISSION = "🚫 The VJ needs {missing} in {channel}. Ask Morgan."

# ---- part 2: the booth (/mc shout, postcards, mode by mode)
STATUS_PER_MODE_NAME = "Mode by mode"
STATUS_MODE_AWAKE = "{mode}: {online} on"
STATUS_MODE_ASLEEP = "{mode}: asleep (joining wakes it)"

SHOUT_OFF = "📡 The booth isn't wired up yet, comrade. Shouting into the game is coming soon."
SHOUT_WAIT = "⏳ Your voice needs a rest. Shout again {when}."
SHOUT_WAIT_EVERYONE = "⏳ Someone just shouted. Let the game chat breathe and try again {when}."
SHOUT_BROKE = "💸 A shout costs **{cost} USh** and you've got **{balance}**. Chat a bit and come back."
SHOUT_EMPTY = "🤐 That shout is empty once the VJ cleans it up. Try some words."
SHOUT_DONE = "📢 {member} shouted into {modes}: {text}"
SHOUT_PAID = "\n-# {cost} USh to the bank."
SHOUT_FREE = "\n-# VIP: on the house."
SHOUT_ASLEEP = " ({modes} asleep)"
SHOUT_NOBODY = "😴 Every screen is dark right now (all modes asleep), so nobody would hear you. No USh taken."
SHOUT_NOTE = "a shout into Minecraft"  # shows in /balance next to the payment
SHOUT_REFUND_NOTE = "shout refund: nobody heard it"
SHOUT_FAILED = "📡 The VJ couldn't reach the booth. No USh taken. Try again in a bit."

POSTCARD_JOIN = "🎟️ **{name}** walked into the cinema for the first time. Welcome to the screening!"
POSTCARD_DEATH = "💀 {text}. The VJ looks away."
POSTCARD_ADVANCEMENT = "🏆 **{name}** unlocked **{title}**."
POSTCARD_OWNER = " ({members})"

POSTCARDS_ON = (
    "📮 Postcards from the server land in {channel}: first-timers (whole network), deaths and advancements (Factions)."
)
POSTCARDS_OFF = "📮 Postcards off."
POSTCARDS_NO_BOOTH = " The booth isn't wired up yet, so they'll start when it is."
