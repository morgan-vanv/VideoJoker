"""The server-list ping: the same question the Minecraft multiplayer screen asks ("are you up, and who's on?").

It's Minecraft's own little protocol over TCP, and small enough to write by hand, which is a nice look at how
games talk on the wire (https://minecraft.wiki/w/Java_Edition_protocol/Server_List_Ping):

  1. We send a "handshake" packet saying which address and port we came for, and that we want the status.
  2. We send an empty "status request" packet.
  3. The server answers with one packet holding a JSON text: version, players online, the message of the day.

Every packet is: its length, its packet id, then its fields. Numbers are "VarInts": 7 bits per byte, and the top
bit says "another byte follows". That way small numbers (most of them) take one byte.

Kuma (Morgan's monitoring) asks the same question every two minutes at the same address, so this is a normal,
polite thing to do. Velocity is set up not to list player names in this answer, only how many.
"""

import asyncio
import json
import struct
from typing import NamedTuple

TIMEOUT_SECONDS = 5
HANDSHAKE_PACKET = 0x00
STATUS_REQUEST_PACKET = 0x00
NEXT_STATE_STATUS = 1
ANY_PROTOCOL = -1  # "I'm only asking for the status", accepted by every version


class ServerStatus(NamedTuple):
    online: int
    max_players: int
    version: str  # e.g. "Velocity 1.7.2-26.3"


class PingFailed(Exception):
    """The server didn't answer (down, unreachable, or it said something we couldn't read)."""


def encode_varint(value: int) -> bytes:
    """A number as a VarInt. Negative numbers are sent as their 32-bit two's complement (always 5 bytes)."""
    value &= 0xFFFFFFFF
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)  # the top bit: "more bytes follow"
        else:
            out.append(byte)
            return bytes(out)


def encode_string(text: str) -> bytes:
    data = text.encode("utf-8")
    return encode_varint(len(data)) + data


def packet(packet_id: int, payload: bytes = b"") -> bytes:
    """Frames a packet: its length first, then its id and fields."""
    body = encode_varint(packet_id) + payload
    return encode_varint(len(body)) + body


def handshake(host: str, port: int) -> bytes:
    payload = (
        encode_varint(ANY_PROTOCOL) + encode_string(host) + struct.pack(">H", port) + encode_varint(NEXT_STATE_STATUS)
    )
    return packet(HANDSHAKE_PACKET, payload)


async def read_varint(reader: asyncio.StreamReader) -> int:
    result = 0
    for position in range(5):  # a VarInt is at most 5 bytes
        (byte,) = await reader.readexactly(1)
        result |= (byte & 0x7F) << (7 * position)
        if not byte & 0x80:
            return result
    raise PingFailed("a number in the answer was too long")


def parse_status(text: str) -> ServerStatus:
    """Pulls what we show out of the server's JSON answer."""
    try:
        data = json.loads(text)
        players = data.get("players", {})
        return ServerStatus(
            online=int(players.get("online", 0)),
            max_players=int(players.get("max", 0)),
            version=str(data.get("version", {}).get("name", "")),
        )
    except (ValueError, AttributeError, TypeError) as error:
        raise PingFailed("the answer wasn't the JSON we expected") from error


async def ping(host: str, port: int) -> ServerStatus:
    """Asks the server for its status. Raises PingFailed if it can't."""
    try:
        return await asyncio.wait_for(_ping(host, port), TIMEOUT_SECONDS)
    except (OSError, asyncio.IncompleteReadError, TimeoutError) as error:
        raise PingFailed(type(error).__name__) from error


async def _ping(host: str, port: int) -> ServerStatus:
    reader, writer = await asyncio.open_connection(host, port)
    try:
        writer.write(handshake(host, port) + packet(STATUS_REQUEST_PACKET))
        await writer.drain()
        await read_varint(reader)  # the answer's length: we read it field by field instead
        if await read_varint(reader) != 0x00:
            raise PingFailed("the server answered with a different packet")
        length = await read_varint(reader)
        text = (await reader.readexactly(length)).decode("utf-8", errors="replace")
        return parse_status(text)
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except OSError:
            pass
