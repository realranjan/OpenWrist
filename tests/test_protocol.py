"""
Unit tests for protocol serialization, deserialization, reassembly, and validation.
"""

import sys
import unittest
from pathlib import Path

# Ensure src/ is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from watchgesture.core.protocol import (
    CHAR_NOTIFY_FEE3,
    CHAR_WRITE_FEE2,
    CMD_CAMERA_ABORT,
    CMD_CAMERA_GESTURE,
    CMD_FIND_MY_WATCH,
    CMD_GSENSOR_CALIBRATION,
    CMD_NOTIFY_PHONE_OPERATION,
    CMD_QUICK_VIEW,
    CMD_SEND_MESSAGE,
    CMD_SET_MUSIC_INFO,
    CMD_SWITCH_CAMERA_VIEW,
    MAGIC_BYTE_1,
    MAGIC_BYTE_2,
    OP_PLAY_PAUSE,
    PacketReassembler,
    PacketV2,
    build_v2_packet,
    is_gesture_notification,
    make_abort_packet,
    make_find_watch_packet,
    make_gsensor_calibration_packet,
    make_heartrate_trigger_packet,
    make_keepalive_packet,
    make_music_info_packet,
    make_quick_view_packet,
    make_screen_message_packet,
    make_spo2_trigger_packet,
    parse_v2_packet,
)


class TestProtocol(unittest.TestCase):
    def test_build_packet_without_payload(self):
        packet = build_v2_packet(0x66)
        self.assertEqual(packet[0], MAGIC_BYTE_1)
        self.assertEqual(packet[1], MAGIC_BYTE_2)
        self.assertEqual(packet[2], 0x20)  # total=5, high byte 0
        self.assertEqual(packet[3], 0x05)  # total=5, low byte 5
        self.assertEqual(packet[4], 0x66)  # cmd
        self.assertEqual(len(packet), 5)

    def test_build_packet_with_payload(self):
        payload = bytes([0x01, 0x02, 0x03])
        packet = build_v2_packet(0x18, payload)
        self.assertEqual(packet[0], MAGIC_BYTE_1)
        self.assertEqual(packet[1], MAGIC_BYTE_2)
        total = 5 + 3
        self.assertEqual(packet[2], 0x20)
        self.assertEqual(packet[3], total)
        self.assertEqual(packet[4], 0x18)
        self.assertEqual(packet[5:], bytearray(payload))

    def test_build_v1_mtu20_packet(self):
        packet = build_v2_packet(0x66, bytes([0x01]), mtu=20)
        self.assertEqual(packet[0], MAGIC_BYTE_1)
        self.assertEqual(packet[1], MAGIC_BYTE_2)
        self.assertEqual(packet[2], 0x10)  # MTU 20 tag
        self.assertEqual(packet[3], 0x06)  # total = 6
        self.assertEqual(packet[4], 0x66)

    def test_parse_valid_packet(self):
        raw = build_v2_packet(0x66, bytes([0x01]))
        parsed = parse_v2_packet(raw)
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed.cmd, 0x66)
        self.assertEqual(parsed.payload, bytes([0x01]))
        self.assertEqual(parsed.total_length, 6)

    def test_parse_invalid_magic_bytes(self):
        corrupt = bytearray([0xAA, 0xBB, 0x20, 0x05, 0x66])
        parsed = parse_v2_packet(corrupt)
        self.assertIsNone(parsed)

    def test_parse_short_packet(self):
        short = bytearray([0xFE, 0xEA, 0x20])
        parsed = parse_v2_packet(short)
        self.assertIsNone(parsed)

    def test_parse_truncated_payload(self):
        truncated = bytearray([0xFE, 0xEA, 0x20, 0x07, 0x66])
        parsed = parse_v2_packet(truncated)
        self.assertIsNone(parsed)

    def test_gesture_notification_detection(self):
        raw_gesture = build_v2_packet(CMD_CAMERA_GESTURE, bytes([0x01]))
        self.assertTrue(is_gesture_notification("0000fee3-0000-1000-8000-00805f9b34fb", raw_gesture))
        self.assertTrue(is_gesture_notification("fee3", raw_gesture))
        # Wrong characteristic
        self.assertFalse(is_gesture_notification("0000fee2-0000-1000-8000-00805f9b34fb", raw_gesture))
        # Wrong command
        raw_other = build_v2_packet(0x18, bytes([0x01]))
        self.assertFalse(is_gesture_notification("fee3", raw_other))

    def test_packet_reassembler_single_packet(self):
        reassembler = PacketReassembler()
        raw = build_v2_packet(CMD_SWITCH_CAMERA_VIEW, bytes([0x01]))
        packets = reassembler.feed(raw)
        self.assertEqual(len(packets), 1)
        self.assertEqual(packets[0].cmd, CMD_SWITCH_CAMERA_VIEW)
        self.assertEqual(packets[0].payload, bytes([0x01]))

    def test_packet_reassembler_chunked_fragments(self):
        reassembler = PacketReassembler()
        # Message packet: 5-byte header + 1-byte type + 11-byte text = 17 bytes
        msg_packet = make_screen_message_packet("Hi", "There")
        # Split into 3 fragments of 6, 6, 5 bytes
        frag1 = msg_packet[:6]
        frag2 = msg_packet[6:12]
        frag3 = msg_packet[12:]

        res1 = reassembler.feed(frag1)
        self.assertEqual(len(res1), 0)

        res2 = reassembler.feed(frag2)
        self.assertEqual(len(res2), 0)

        res3 = reassembler.feed(frag3)
        self.assertEqual(len(res3), 1)
        self.assertEqual(res3[0].cmd, CMD_SEND_MESSAGE)
        self.assertTrue(b"Hi:There" in res3[0].payload)

    def test_packet_reassembler_corrupt_leading_byte_resync(self):
        reassembler = PacketReassembler()
        valid = build_v2_packet(CMD_SWITCH_CAMERA_VIEW, bytes([0x01]))
        corrupt_stream = b"\xFF\xAA" + bytes(valid)
        packets = reassembler.feed(corrupt_stream)
        self.assertEqual(len(packets), 1)
        self.assertEqual(packets[0].cmd, CMD_SWITCH_CAMERA_VIEW)

    def test_helper_builders(self):
        keepalive = make_keepalive_packet()
        self.assertEqual(keepalive, bytearray([0xFE, 0xEA, 0x20, 0x06, 0x66, 0x01]))

        abort_pkt = make_abort_packet()
        self.assertEqual(abort_pkt, bytearray([0xFE, 0xEA, 0x20, 0x05, 0x53]))

        qv_enabled = make_quick_view_packet(True)
        self.assertEqual(qv_enabled, bytearray([0xFE, 0xEA, 0x20, 0x06, 0x18, 0x01]))

        buzz = make_find_watch_packet()
        self.assertEqual(buzz, bytearray([0xFE, 0xEA, 0x20, 0x05, 0x61]))

        zero_accel = make_gsensor_calibration_packet()
        self.assertEqual(zero_accel, bytearray([0xFE, 0xEA, 0x20, 0x05, 0x52]))

        hr = make_heartrate_trigger_packet(True)
        self.assertEqual(hr, bytearray([0xFE, 0xEA, 0x20, 0x06, 0x6D, 0x00]))

        spo2 = make_spo2_trigger_packet(True)
        self.assertEqual(spo2, bytearray([0xFE, 0xEA, 0x20, 0x06, 0x6B, 0x00]))

        music = make_music_info_packet("Track", "Artist")
        self.assertEqual(music[4], CMD_SET_MUSIC_INFO)
        self.assertTrue(b"Track - Artist" in music)


if __name__ == "__main__":
    unittest.main()
