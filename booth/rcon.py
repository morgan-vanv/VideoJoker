"""A tiny RCON client: how the booth types commands into a Minecraft server's console from outside.

RCON ("remote console") is Valve's old Source protocol, which Minecraft adopted. Every packet is:

    length (4 bytes) | request id (4 bytes) | type (4 bytes) | body text | two zero bytes

all little-endian ("<i" in struct's language). First we send our password as an AUTH packet; the server answers
with the same request id if it's right, or -1 if it's wrong. Then each COMMAND packet gets one RESPONSE packet
back with the console's answer.

We open a fresh connection for every command and close it after. Slower than keeping one open, but much simpler:
a mode that's asleep (stopped to save memory) just refuses the connection, and we skip it.
"""

# The booth ships as its own image and never imports the bot, so the few lines it shares with minecraft/ping.py
# (closing a connection) are copied on purpose.
# pylint: disable=duplicate-code

import asyncio
import struct

AUTH = 3
AUTH_RESPONSE = 2
COMMAND = 2
RESPONSE = 0
TIMEOUT_SECONDS = 3


class RconUnavailable(Exception):
    """Nobody answered: the mode is asleep, restarting, or unreachable. Callers skip it quietly."""


class RconRefused(Exception):
    """The server answered but refused our password. That's a setup problem, not a sleeping mode."""


def encode(request_id: int, packet_type: int, body: str) -> bytes:
    payload = struct.pack("<ii", request_id, packet_type) + body.encode("utf-8") + b"\x00\x00"
    return struct.pack("<i", len(payload)) + payload


async def read_packet(reader: asyncio.StreamReader) -> tuple[int, int, str]:
    """One packet: (request id, type, body)."""
    (length,) = struct.unpack("<i", await reader.readexactly(4))
    if not 10 <= length <= 1024 * 1024:
        raise RconUnavailable("a packet with a strange length")
    data = await reader.readexactly(length)
    request_id, packet_type = struct.unpack("<ii", data[:8])
    return request_id, packet_type, data[8:-2].decode("utf-8", errors="replace")


async def run(host: str, port: int, password: str, command: str) -> str:
    """Runs one console command and returns the console's answer.
    Raises RconUnavailable (skip this mode) or RconRefused (wrong password)."""
    try:
        return await asyncio.wait_for(_run(host, port, password, command), TIMEOUT_SECONDS)
    except (OSError, asyncio.IncompleteReadError, TimeoutError) as error:
        raise RconUnavailable(type(error).__name__) from error


async def _run(host: str, port: int, password: str, command: str) -> str:
    reader, writer = await asyncio.open_connection(host, port)
    try:
        writer.write(encode(1, AUTH, password))
        await writer.drain()
        request_id, packet_type, _ = await read_packet(reader)
        if packet_type == RESPONSE:  # some servers send an empty RESPONSE before the AUTH_RESPONSE
            request_id, packet_type, _ = await read_packet(reader)
        if request_id == -1:
            raise RconRefused("the RCON password was refused")
        writer.write(encode(2, COMMAND, command))
        await writer.drain()
        _, _, body = await read_packet(reader)
        return body
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except OSError:
            pass
