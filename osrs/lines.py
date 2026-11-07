"""Everything the VJ says for the OSRS features, in one place. Edit freely: it's just text.

{curly} bits are filled in by the code with .format(...).
"""

CLAN_NAME = "Ugandans"
DINK_SETTINGS_URL = "https://raw.githubusercontent.com/morgan-vanv/VideoJoker/main/osrs/dink-settings.json"

# ---- /osrs register
INVALID_RSN = "🚫 **{rsn}** can't be an OSRS name. Names are 1–12 letters, numbers, spaces, `-` or `_`."
REGISTERED = "✅ **{rsn}** is now one of your accounts."
REGISTERED_DEFAULT = " It's your default."
ALREADY_YOURS = "👍 **{rsn}** is already one of your accounts."
TAKEN = "🚫 **{rsn}** is already registered to {owner}. If that's wrong, ask them to `/osrs remove` it."

# ---- the clan question
CLAN_QUESTION = "🏰 Is **{rsn}** joining the clan?"
CLAN_JOIN = "🏰 In game, join the **{clan}** clan chat and apply. A ranked member will take it from there."
CLAN_ALREADY = "🏰 A true Ugandan. Noted. The VJ won't ask again."
CLAN_NO = "🏰 No problem. The door stays open, comrade."

# ---- flexing
FLEX_QUESTION = "💰 Want your drops flexed in {channel}?"
FLEX_YES = "💰 The VJ readies the projector."
DEATHS_QUESTION = "💀 And your deaths? Want them in {channel}, so everyone can point and laugh?"
DEATHS_YES = "💀 Brave. Sit respectfully."
DEATHS_NO = "💀 Your deaths stay between you and the VJ."
FLEX_LATER = "💰 Whenever you're ready: `/osrs flexing`."
FLEX_NOT_SET_UP = "🚧 Flexing isn't set up on this server yet (the bot needs `OSRS_FLEXING_CHANNEL_ID`)."
FLEX_NO_PERMISSION = "🚫 The VJ needs the **Manage Webhooks** permission in {channel} to run flexing. Ask Morgan."
FLEX_KIT_TITLE = (
    "## 💰 Your flexing kit\nIn RuneLite, open the **Dink** plugin's settings (install it from the Plugin Hub first):"
)
FLEX_KIT_PRIMARY = "**1.** **Primary Webhook URLs**: delete anything already there, then paste:\n```\n{url}\n```"
FLEX_KIT_DEATHS = (
    "**2.** **Death** section: tick **Enable Death**. Then **Webhook Overrides → Death Webhook Override**: paste:"
    "\n```\n{url}\n```Leave the other override boxes empty."
)
FLEX_KIT_NO_DEATHS = (
    "**2.** **Death** section: untick **Enable Death**. And make sure every **Webhook Overrides** box is empty "
    "(the old setup sent deaths elsewhere)."
)
FLEX_KIT_SETTINGS = (
    "**3.** **Advanced → Dynamic Config URL**: replace whatever's there with:\n```\n{url}\n```"
    "That keeps your settings in step with everyone's. Close and reopen the panel, then go get that drop."
)
FLEX_KIT_SECRET = (
    "-# 🤫 The webhook link is a key to the channel: don't share it or post it anywhere. "
    "If it leaks, a VIP can replace it with `/osrs rotate-webhook`."
)

# ---- /osrs accounts, /osrs whois, /osrs default, /osrs remove
NO_ACCOUNTS = "You haven't registered any OSRS accounts yet. Start with `/osrs register`."
NOT_YOURS = "🚫 You don't have **{rsn}** registered. `/osrs accounts` shows what you do have."
NEW_DEFAULT = "⭐ **{rsn}** is now your default."
REMOVED = "🗑️ **{rsn}** is no longer one of your accounts."
WHOIS_NOBODY = "{member} hasn't registered any OSRS accounts."
ACCOUNTS_LEGEND = "⭐ default · 🏰 in the clan"

# ---- /osrs rotate-webhook
ROTATED_PING = "📽️ New flexing link: the old one no longer works. {mentions}: run `/osrs flexing` to get yours."
ROTATED_DONE = "🔄 Done: the old webhook is gone and a fresh one is up. Pinged {count} flexer(s) in {channel}."
