"""The Minecraft network the bot points people at. One network for the dev and the prod bot, so it lives in code
(like the OSRS clan's Wise Old Man group), not in .env.

The network itself is set up in Morgan's infrastructure repo: a Velocity proxy with Geyser, so Java and Bedrock
players join the same servers. Everyone lands in the hub first and picks a mode from its menu.
"""

ADDRESS = "mc.morganvanv.com"
JAVA_PORT = 25565  # Java's default, so players type just the address
BEDROCK_PORT = 19132  # Bedrock's default; its "add server" screen asks for it anyway
MAX_PLAYERS_SHOWN = 50  # Velocity's show-max-players

# The modes, in the order the menu shows them: (key for buttons, name). Their blurbs are in minecraft/lines.py.
MODES = (("factions", "Factions"), ("anarchy", "Anarchy"), ("creative", "Creative"))
