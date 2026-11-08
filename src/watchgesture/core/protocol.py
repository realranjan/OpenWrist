"""
Bluetooth Low Energy Protocol Specifications for MoYoung-v2 / DaFit / Fire-Boltt smartwatches.

Encapsulates complete reverse-engineered GATT services, opcodes, packet reassembly,
and command serialization for the vendor-specific 0xFEEA service family (Realtek RTL8762 SoCs).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple, Union

# --- GATT Service & Characteristic UUIDs ---
SERVICE_FEEA: str = "0000feea-0000-1000-8000-00805f9b34fb"
CHAR_STEPS_FEE1: str = "0000fee1-0000-1000-8000-00805f9b34fb"     # Read / Notify pedometer data
CHAR_WRITE_FEE2: str = "0000fee2-0000-1000-8000-00805f9b34fb"     # Control write pipe (commands)
CHAR_NOTIFY_FEE3: str = "0000fee3-0000-1000-8000-00805f9b34fb"    # Notification pipe (responses & sensor events)
CHAR_DATA_FEE6: str = "0000fee6-0000-1000-8000-00805f9b34fb"      # Bulk data pipe (watchfaces & assets)
CHAR_BATTERY_2A19: str = "00002a19-0000-1000-8000-00805f9b34fb"   # Standard Battery Level
CHAR_MANUFACTURER_2A29: str = "00002a29-0000-1000-8000-00805f9b34fb"  # Reads "MOYOUNG-V2"

# --- Protocol Framing Constants ---
MAGIC_BYTE_1: int = 0xFE
MAGIC_BYTE_2: int = 0xEA
HEADER_LEN: int = 5
DEFAULT_MTU: int = 247

# --- Firmware Command Opcodes (MoYoung / DaFit Standard) ---

# Camera & Screen Navigation
CMD_RETURN_HOME: int = 83               # 0x53: Out {} return home; In: camera view closed
CMD_SWITCH_CAMERA_VIEW: int = 102       # 0x66: Out {} arms G-sensor; In: wrist flick / shutter event
CMD_CAMERA_GESTURE: int = 102          # Alias for 0x66
CMD_CAMERA_ABORT: int = 83             # Alias for 0x53

# Phone Interaction & Media Controls (Incoming from Watch screen/buttons)
CMD_NOTIFY_PHONE_OPERATION: int = 103   # 0x67: Watch media & call controls
CMD_FIND_MY_PHONE: int = 98            # 0x62: Incoming {0} start / {!=0} stop
CMD_FIND_MY_WATCH: int = 97            # 0x61: Out {} causes watch to buzz/vibrate
CMD_GSENSOR_CALIBRATION: int = 82      # 0x52: Out {} zeroes the watch accelerometer

# Media Operations (Arguments for CMD_NOTIFY_PHONE_OPERATION)
OP_PLAY_PAUSE: int = 0
OP_PREV_SONG: int = 1
OP_NEXT_SONG: int = 2
OP_DROP_INCOMING_CALL: int = 3
OP_VOLUME_UP: int = 4
OP_VOLUME_DOWN: int = 5
OP_PLAY: int = 6
OP_PAUSE: int = 7
OP_SEND_CURRENT_VOLUME: int = 12

PHONE_OPERATIONS_MAP: Dict[int, str] = {
    OP_PLAY_PAUSE: "play_pause",
    OP_PREV_SONG: "previous_track",
    OP_NEXT_SONG: "next_track",
    OP_DROP_INCOMING_CALL: "drop_call",
    OP_VOLUME_UP: "volume_up",
    OP_VOLUME_DOWN: "volume_down",
    OP_PLAY: "play",
    OP_PAUSE: "pause",
}

# Messaging & Display Injection
CMD_SEND_MESSAGE: int = 65             # 0x41: Push notification string to watch screen
CMD_SYNC_TIME: int = 49                # 0x31: Synchronize watch real-time clock
CMD_SET_WEATHER_TODAY: int = 67        # 0x43: Inject temperature into watch face
CMD_SET_WEATHER_FUTURE: int = 66       # 0x42: 7-day forecast
CMD_SET_MUSIC_INFO: int = 68           # 0x44: Display artist / title on watch screen
CMD_SET_MUSIC_STATE: int = 123         # 0x7B: {1} playing, {0} paused

# Health & Sensor Measurement Triggers
CMD_TRIGGER_MEASURE_HEARTRATE: int = 109    # 0x6D: {0} start / {0xFF} stop -> returns bpm
CMD_TRIGGER_MEASURE_BLOOD_OXYGEN: int = 107 # 0x6B: {0} start / {0xFF} stop -> returns % SpO2
CMD_TRIGGER_MEASURE_BLOOD_PRESSURE: int = 105 # 0x69: {0,0,0} start -> returns {sys, dia}
CMD_START_STOP_MEASURE_DYNAMIC_RATE: int = 104 # 0x68: Continuous HR stream

# Settings & Power
CMD_SET_QUICK_VIEW: int = 24           # 0x18: Raise-to-wake toggle {1=on, 0=off}
CMD_QUICK_VIEW: int = 24               # Backward-compatible alias
CMD_QUERY_QUICK_VIEW: int = 40         # 0x28: Query raise-to-wake state
CMD_QUERY_DEVICE_VERSION: int = 46     # 0x2E: Firmware version query
CMD_SET_POWER_SAVING: int = 0x94       # 148: Power saving mode toggle
CMD_SHUTDOWN: int = 81                 # 0x51: {0xFF} powers watch off

# Watch clock timezone (MoYoung firmwares are hardwired to GMT+8 internally)
_WATCH_TZ = timezone(timedelta(hours=8))


@dataclass(frozen=True)
class PacketV2:
    """Represents a validated, parsed DaFit / MoYoung V2 protocol packet."""
    cmd: int
    payload: bytes
    raw: bytes

    @property
    def total_length(self) -> int:
        return len(self.raw)

    def __repr__(self) -> str:
        return f"PacketV2(cmd=0x{self.cmd:02X} ({self.cmd}), len={self.total_length}, payload={self.payload.hex()})"


def parse_packet_length(buf: Union[bytes, bytearray]) -> int:
    """
    Computes total packet length from header, or returns -1 if invalid.
    Supports both MTU=20 (v1 framing: 0x10) and MTU>20 (v2 framing: 0x20 + (len>>8)).
    """
    if len(buf) < 4 or buf[0] != MAGIC_BYTE_1 or buf[1] != MAGIC_BYTE_2:
        return -1

    b2 = buf[2]
    if b2 == 0x10:
        len_h = 0
    else:
        if b2 < 0x20:
            return -1
        len_h = b2 - 0x20

    return (len_h << 8) | buf[3]


def build_v2_packet(cmd: int, payload: Union[bytes, bytearray] = b"", mtu: int = DEFAULT_MTU) -> bytearray:
    """
    Constructs a framed V1 or V2 packet with header, length bytes, opcode, and payload.
    """
    payload_bytes = bytes(payload)
    total = HEADER_LEN + len(payload_bytes)

    if mtu == 20:
        b2 = 0x10
    else:
        b2 = (0x20 + (total >> 8)) & 0xFF

    b3 = total & 0xFF
    return bytearray([MAGIC_BYTE_1, MAGIC_BYTE_2, b2, b3, cmd & 0xFF]) + bytearray(payload_bytes)


def parse_v2_packet(data: Union[bytes, bytearray]) -> Optional[PacketV2]:
    """
    Validates and decodes raw byte stream into a structured PacketV2 instance.
    Returns None if the data fails magic byte or length integrity checks.
    """
    raw = bytes(data)
    total = parse_packet_length(raw)
    if total < HEADER_LEN or len(raw) < total:
        return None

    cmd = raw[4]
    payload = raw[HEADER_LEN:total]
    return PacketV2(cmd=cmd, payload=payload, raw=raw[:total])


class PacketReassembler:
    """
    Reassembles incoming BLE notification byte fragments (characteristic 0xFEE3)
    into complete PacketV2 frames, preventing data loss across BLE MTU chunk splits.
    """

    def __init__(self) -> None:
        self._buf = bytearray()

    def feed(self, fragment: Union[bytes, bytearray]) -> List[PacketV2]:
        """Ingests raw fragment and yields all newly completed packets."""
        self._buf += fragment
        packets: List[PacketV2] = []

        while len(self._buf) >= 4:
            total = parse_packet_length(self._buf)
            if total < HEADER_LEN:
                # Corrupt magic byte or bad header; advance 1 byte to resynchronize stream
                del self._buf[0]
                continue

            if len(self._buf) < total:
                # More fragments needed for complete frame
                break

            packet_bytes = bytes(self._buf[:total])
            del self._buf[:total]

            parsed = parse_v2_packet(packet_bytes)
            if parsed is not None:
                packets.append(parsed)

        return packets


def is_gesture_notification(char_uuid: str, data: Union[bytes, bytearray]) -> bool:
    """Checks whether notification represents an active wrist flick event (Opcode 0x66 on FEE3)."""
    if "fee3" not in char_uuid.lower():
        return False
    packet = parse_v2_packet(data)
    return packet is not None and packet.cmd == CMD_SWITCH_CAMERA_VIEW


# --- High-Level Payload Builders ---

def make_keepalive_packet() -> bytearray:
    """Periodic 6-second heartbeat packet that keeps the G-Sensor streaming."""
    return build_v2_packet(CMD_SWITCH_CAMERA_VIEW, bytes([0x01]))


def make_abort_packet() -> bytearray:
    """Cancels camera view shutter animation for immediate re-arming."""
    return build_v2_packet(CMD_RETURN_HOME, b"")


def make_find_watch_packet() -> bytearray:
    """Causes the watch to vibrate / buzz immediately (Find Watch)."""
    return build_v2_packet(CMD_FIND_MY_WATCH, b"")


def make_gsensor_calibration_packet() -> bytearray:
    """Commands the watch to calibrate and zero its internal 3-axis accelerometer."""
    return build_v2_packet(CMD_GSENSOR_CALIBRATION, b"")


def make_quick_view_packet(enable: bool) -> bytearray:
    """Opcode 0x18 packet to enable or disable Raise-To-Wake."""
    return build_v2_packet(CMD_SET_QUICK_VIEW, bytes([0x01 if enable else 0x00]))


def make_screen_message_packet(title: str, body: str, msg_type: int = 11) -> bytearray:
    """
    Pushes an on-screen notification alert to the watch display.
    The watch parses the first colon as the title/body separator.
    """
    text = f"{title}:{body}"
    payload = bytes([msg_type & 0xFF]) + text.encode("utf-8")
    return build_v2_packet(CMD_SEND_MESSAGE, payload)


def make_music_info_packet(track_title: str, artist: str = "") -> bytearray:
    """Displays now-playing media information directly on the watch screen."""
    display_text = f"{track_title} - {artist}" if artist else track_title
    payload = bytes([0x00]) + display_text.encode("utf-8")
    return build_v2_packet(CMD_SET_MUSIC_INFO, payload)


def make_heartrate_trigger_packet(start: bool = True) -> bytearray:
    """Starts or stops an on-demand heart-rate reading."""
    return build_v2_packet(CMD_TRIGGER_MEASURE_HEARTRATE, bytes([0x00 if start else 0xFF]))


def make_spo2_trigger_packet(start: bool = True) -> bytearray:
    """Starts or stops an on-demand SpO2 blood oxygen reading."""
    return build_v2_packet(CMD_TRIGGER_MEASURE_BLOOD_OXYGEN, bytes([0x00 if start else 0xFF]))
