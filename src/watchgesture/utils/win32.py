"""
Native Windows Virtual-Key injection utilities using Win32 API.

Provides direct hardware-level keystroke delivery via user32.keybd_event,
ensuring low latency and reliable registration even in games or full-screen browsers.
"""

from __future__ import annotations

import sys
import time
from typing import Sequence

IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    import ctypes
    _user32 = ctypes.windll.user32
else:
    _user32 = None

# Standard Win32 Virtual Key Codes
VK_BACK: int = 0x08
VK_TAB: int = 0x09
VK_RETURN: int = 0x0D
VK_ESCAPE: int = 0x1B
VK_SPACE: int = 0x20
VK_LEFT: int = 0x25
VK_UP: int = 0x26
VK_RIGHT: int = 0x27
VK_DOWN: int = 0x28
VK_LWIN: int = 0x5B
VK_RWIN: int = 0x5C
VK_D: int = 0x44
VK_M: int = 0x4D
VK_B: int = 0x42
VK_MEDIA_NEXT_TRACK: int = 0xB0
VK_MEDIA_PREV_TRACK: int = 0xB1
VK_MEDIA_STOP: int = 0xB2
VK_MEDIA_PLAY_PAUSE: int = 0xB3
VK_VOLUME_MUTE: int = 0xAD
VK_VOLUME_DOWN: int = 0xAE
VK_VOLUME_UP: int = 0xAF

KEYEVENTF_KEYUP: int = 0x0002


def send_virtual_key(vk_code: int, hold_sec: float = 0.02) -> None:
    """
    Sends a keydown followed by keyup for the specified virtual key code.
    Safely no-ops if not running on Windows.
    """
    if not IS_WINDOWS or _user32 is None:
        return

    _user32.keybd_event(vk_code, 0, 0, 0)
    time.sleep(hold_sec)
    _user32.keybd_event(vk_code, 0, KEYEVENTF_KEYUP, 0)


def send_virtual_hotkey(vk_sequence: Sequence[int], hold_sec: float = 0.02) -> None:
    """
    Presses all keys in sequence, holds briefly, and releases them in reverse order.
    """
    if not IS_WINDOWS or _user32 is None:
        return

    for vk in vk_sequence:
        _user32.keybd_event(vk, 0, 0, 0)

    time.sleep(hold_sec)

    for vk in reversed(vk_sequence):
        _user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)


def send_win_d() -> None:
    """Dispatches the Windows + D shortcut to instantly show or hide the desktop."""
    send_virtual_hotkey([VK_LWIN, VK_D])

