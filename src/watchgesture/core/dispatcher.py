"""
Action Dispatcher for WatchGesture.

Translates classified gesture counts into keystrokes, shortcuts, and media commands
using PyAutoGUI and native Win32 keyboard event injection.
"""

from __future__ import annotations

import logging
import time
from typing import Callable, Optional

import pyautogui

from watchgesture.core.engine import GestureEvent
from watchgesture.profiles.default_profiles import ActionItem, GestureProfile
from watchgesture.utils.win32 import send_virtual_hotkey, send_virtual_key, send_win_d

logger = logging.getLogger(__name__)

# Prevent PyAutoGUI failsafe corner-trip exceptions during fullscreen media
pyautogui.FAILSAFE = False


class ActionDispatcher:
    """Dispatches simulated OS inputs mapped to gesture counts."""

    def __init__(
        self,
        profile: GestureProfile,
        on_action_dispatched: Optional[Callable[[ActionItem, str], None]] = None,
    ) -> None:
        self.profile = profile
        self.on_action_dispatched = on_action_dispatched

    def set_profile(self, profile: GestureProfile) -> None:
        """Switches the active mapping profile."""
        self.profile = profile

    def dispatch(self, event: GestureEvent) -> Optional[ActionItem]:
        """
        Executes the input action assigned to the given gesture event.
        Returns the triggered ActionItem or None if unmapped.
        """
        action = self.profile.get_action(event.count)
        if not action:
            logger.warning("No action mapped for gesture count %d in profile %s", event.count, self.profile.name)
            return None

        now_str = time.strftime("%H:%M:%S")

        try:
            self._execute_action_item(action)
        except Exception as exc:
            logger.error("Failed to execute action %s: %s", action.name, exc)

        if self.on_action_dispatched:
            self.on_action_dispatched(action, now_str)

        return action

    def _execute_action_item(self, action: ActionItem) -> None:
        """Internal runner for executing specific action types."""
        # Special shortcut for Win+D Boss Key
        if action.keys == ["win", "d"]:
            send_win_d()
            return

        if action.action_type == "vk" and action.vk_codes:
            send_virtual_hotkey(action.vk_codes)
            return

        if action.action_type == "hotkey" and len(action.keys) > 1:
            pyautogui.hotkey(*action.keys)
            return

        # Default single key press
        for key in action.keys:
            pyautogui.press(key)

