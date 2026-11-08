"""
Unit tests for BTSnoop and BTSnooz bugreport log extraction utilities.
"""

import base64
import struct
import sys
import unittest
import zlib
from pathlib import Path

# Ensure src/ is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from watchgesture.utils.snoop import (
    TYPE_IN_ACL,
    TYPE_IN_EVT,
    TYPE_OUT_CMD,
    decode_btsnooz,
    extract_btsnooz_from_text,
    type_to_direction,
    type_to_hci,
)


class TestSnoop(unittest.TestCase):
    def test_direction_and_hci_mapping(self):
        self.assertEqual(type_to_direction(TYPE_IN_EVT), 1)
        self.assertEqual(type_to_direction(TYPE_IN_ACL), 1)
        self.assertEqual(type_to_direction(TYPE_OUT_CMD), 0)

        self.assertEqual(type_to_hci(TYPE_OUT_CMD), b"\x01")
        self.assertEqual(type_to_hci(TYPE_IN_ACL), b"\x02")
        self.assertEqual(type_to_hci(TYPE_IN_EVT), b"\x04")

        with self.assertRaises(ValueError):
            type_to_hci(0xFF)

    def test_extract_btsnooz_from_text(self):
        raw_payload = b"test_btsnooz_binary_content"
        b64_payload = base64.b64encode(raw_payload).decode("ascii")

        dummy_bugreport = (
            "Build fingerprint: google/taimen/taimen:8.1.0\n"
            "--- BEGIN:BTSNOOP_LOG_SUMMARY\n"
            f"{b64_payload}\n"
            "--- END:BTSNOOP_LOG_SUMMARY\n"
            "Remaining bugreport output..."
        )

        extracted = extract_btsnooz_from_text(dummy_bugreport)
        self.assertEqual(extracted, raw_payload)

    def test_extract_btsnooz_missing_tags(self):
        no_tags = "No btsnoop summary here."
        self.assertIsNone(extract_btsnooz_from_text(no_tags))

    def test_decode_btsnooz_v1_synthetic(self):
        # Version 1 header: version (1 byte = 1), last_timestamp_ms (8 bytes unsigned Q)
        header = struct.pack("=bQ", 1, 1000)

        # Record: length (H), delta_time_ms (I), type (b) + payload (length - 1 bytes)
        # payload length = 4 -> length = 5
        rec_data = b"DATA"
        record = struct.pack("=HIb", len(rec_data) + 1, 50, TYPE_IN_EVT) + rec_data
        compressed = zlib.compress(record)
        snooz_data = header + compressed

        btsnoop_bytes = decode_btsnooz(snooz_data)
        # Wireshark BTSnoop magic header
        self.assertTrue(btsnoop_bytes.startswith(b"btsnoop\x00\x00\x00\x00\x01\x00\x00\x03\xea"))

    def test_decode_btsnooz_invalid_data(self):
        with self.assertRaises(ValueError):
            decode_btsnooz(b"short")

        invalid_version = struct.pack("=bQ", 99, 1000) + zlib.compress(b"")
        with self.assertRaises(ValueError):
            decode_btsnooz(invalid_version)


if __name__ == "__main__":
    unittest.main()

