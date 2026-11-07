"""The read-ahead buffer between yt-dlp and ffmpeg (music/stream.py). No network, no ffmpeg: a BytesIO stands in
for yt-dlp's output pipe."""

import io

from music.stream import _ReadAhead


def test_read_ahead_hands_over_every_byte_in_order():
    song = bytes(range(256)) * 1000  # 256 KB, more than one CHUNK
    buffer = _ReadAhead(io.BytesIO(song))
    received = b""
    while piece := buffer.read(8192):
        assert len(piece) <= 8192
        received += piece
    assert received == song
    assert buffer.received == len(song)


def test_wait_for_returns_once_the_download_ends_even_if_short():
    buffer = _ReadAhead(io.BytesIO(b"tiny song"))
    buffer.wait_for(64 * 1024, timeout=5)  # asks for more than there is: must not wait the full 5 s
    assert buffer.read() == b"tiny song"
    assert buffer.read() == b""  # the end


def test_close_ends_reading():
    buffer = _ReadAhead(io.BytesIO(b"x" * 100))
    buffer.close()
    assert buffer.read() == b""
