"""
BTSnoop and BTSnooz bugreport extraction utilities.

Enables reverse-engineering BLE packets from Android bug reports without
requiring a dedicated hardware Bluetooth sniffer dongle.
"""

from __future__ import annotations

import base64
import struct
import zlib
from typing import Optional, Tuple

TYPE_IN_EVT = 0x10
TYPE_IN_ACL = 0x11
TYPE_IN_SCO = 0x12
TYPE_IN_ISO = 0x17
TYPE_OUT_CMD = 0x20
TYPE_OUT_ACL = 0x21
TYPE_OUT_SCO = 0x22
TYPE_OUT_ISO = 0x2D


def type_to_direction(packet_type: int) -> int:
    """Returns 1 for inbound packets, 0 for outbound packets."""
    if packet_type in (TYPE_IN_EVT, TYPE_IN_ACL, TYPE_IN_SCO, TYPE_IN_ISO):
        return 1
    return 0


def type_to_hci(packet_type: int) -> bytes:
    """Returns the HCI packet indicator byte."""
    if packet_type == TYPE_OUT_CMD:
        return b"\x01"
    if packet_type in (TYPE_IN_ACL, TYPE_OUT_ACL):
        return b"\x02"
    if packet_type in (TYPE_IN_SCO, TYPE_OUT_SCO):
        return b"\x03"
    if packet_type == TYPE_IN_EVT:
        return b"\x04"
    if packet_type in (TYPE_IN_ISO, TYPE_OUT_ISO):
        return b"\x05"
    raise ValueError(f"Unknown btsnooz packet type: 0x{packet_type:02X}")


def decode_btsnooz(snooz_data: bytes) -> bytes:
    """
    Decodes raw btsnooz binary data into Wireshark-compatible btsnoop binary format.
    """
    if len(snooz_data) < 9:
        raise ValueError("Invalid btsnooz data: shorter than header length.")

    version, last_timestamp_ms = struct.unpack_from("=bQ", snooz_data)
    if version not in (1, 2):
        raise ValueError(f"Unsupported btsnooz version: {version}")

    decompressed = zlib.decompress(snooz_data[9:])
    output = bytearray(b"btsnoop\x00\x00\x00\x00\x01\x00\x00\x03\xea")

    if version == 1:
        _decode_v1(decompressed, last_timestamp_ms, output)
    else:
        _decode_v2(decompressed, last_timestamp_ms, output)

    return bytes(output)


def _decode_v1(decompressed: bytes, last_timestamp_ms: int, output: bytearray) -> None:
    first_timestamp_ms = last_timestamp_ms + 0x00DCDDB30F2F8000
    offset = 0
    while offset < len(decompressed):
        length, delta_time_ms, p_type = struct.unpack_from("=HIb", decompressed, offset)
        offset += 7 + length - 1
        first_timestamp_ms -= delta_time_ms

    offset = 0
    while offset < len(decompressed):
        length, delta_time_ms, p_type = struct.unpack_from("=HIb", decompressed, offset)
        first_timestamp_ms += delta_time_ms
        offset += 7
        output.extend(struct.pack(">II", length, length))
        output.extend(struct.pack(">II", type_to_direction(p_type), 0))
        output.extend(struct.pack(">II", (first_timestamp_ms >> 32), (first_timestamp_ms & 0xFFFFFFFF)))
        output.extend(type_to_hci(p_type))
        output.extend(decompressed[offset:offset + length - 1])
        offset += length - 1


def _decode_v2(decompressed: bytes, last_timestamp_ms: int, output: bytearray) -> None:
    first_timestamp_ms = last_timestamp_ms + 0x00DCDDB30F2F8000
    offset = 0
    while offset < len(decompressed):
        length, packet_length, delta_time_ms, snooz_type = struct.unpack_from("=HHIb", decompressed, offset)
        offset += 9 + length - 1
        first_timestamp_ms -= delta_time_ms

    offset = 0
    while offset < len(decompressed):
        length, packet_length, delta_time_ms, snooz_type = struct.unpack_from("=HHIb", decompressed, offset)
        first_timestamp_ms += delta_time_ms
        offset += 9
        output.extend(struct.pack(">II", packet_length, length))
        output.extend(struct.pack(">II", type_to_direction(snooz_type), 0))
        output.extend(struct.pack(">II", (first_timestamp_ms >> 32), (first_timestamp_ms & 0xFFFFFFFF)))
        output.extend(type_to_hci(snooz_type))
        output.extend(decompressed[offset:offset + length - 1])
        offset += length - 1


def extract_btsnooz_from_text(content: str) -> Optional[bytes]:
    """Extracts and base64-decodes btsnooz section from Android bug report text."""
    start_tag = "--- BEGIN:BTSNOOP_LOG_SUMMARY"
    end_tag = "--- END:BTSNOOP_LOG_SUMMARY"

    start_idx = content.find(start_tag)
    if start_idx == -1:
        return None

    end_idx = content.find(end_tag, start_idx)
    if end_idx == -1:
        return None

    raw_b64 = content[start_idx + len(start_tag):end_idx].replace("\n", "").replace("\r", "").strip()
    try:
        return base64.b64decode(raw_b64)
    except Exception:
        return None

