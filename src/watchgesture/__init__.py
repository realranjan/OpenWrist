"""
WatchGesture - Smartwatch BLE Wrist-Gesture Controller.

A modular, zero-lag Bluetooth Low Energy controller that translates
smartwatch wrist flicks (Fire-Boltt / DaFit / Moyoung chipsets) into
programmable desktop keyboard and media actions.
"""

__version__ = "1.0.0"
__author__ = "WatchGesture Contributors"

from watchgesture.config import AppConfig, GestureProfile
from watchgesture.core.protocol import (
    SERVICE_FEEA,
    CHAR_WRITE_FEE2,
    CHAR_NOTIFY_FEE3,
    CMD_CAMERA_GESTURE,
    CMD_CAMERA_ABORT,
    CMD_QUICK_VIEW,
    PacketV2,
    build_v2_packet,
    parse_v2_packet,
)
from watchgesture.core.engine import GestureEngine, GestureEvent
from watchgesture.core.dispatcher import ActionDispatcher
from watchgesture.core.client import WatchGestureClient

__all__ = [
    "__version__",
    "AppConfig",
    "GestureProfile",
    "SERVICE_FEEA",
    "CHAR_WRITE_FEE2",
    "CHAR_NOTIFY_FEE3",
    "CMD_CAMERA_GESTURE",
    "CMD_CAMERA_ABORT",
    "CMD_QUICK_VIEW",
    "PacketV2",
    "build_v2_packet",
    "parse_v2_packet",
    "GestureEngine",
    "GestureEvent",
    "ActionDispatcher",
    "WatchGestureClient",
]

