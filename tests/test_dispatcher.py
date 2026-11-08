"""
Unit tests for Action Dispatcher input mapping and execution callbacks.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure src/ is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from watchgesture.core.dispatcher import ActionDispatcher
from watchgesture.core.engine import GestureEvent
from watchgesture.profiles.default_profiles import BUILTIN_PROFILES


class TestDispatcher(unittest.TestCase):
    def setUp(self):
        self.dispatched = []

        def on_dispatched(action, now_str):
            self.dispatched.append((action, now_str))

        self.profile = BUILTIN_PROFILES["reels"]
        self.dispatcher = ActionDispatcher(self.profile, on_action_dispatched=on_dispatched)

    @patch("watchgesture.core.dispatcher.pyautogui.press")
    def test_dispatch_single_flick(self, mock_press):
        event = GestureEvent(count=1, timestamp=1000.0, trigger_type="timeout")
        action = self.dispatcher.dispatch(event)
        self.assertIsNotNone(action)
        assert action is not None
        self.assertEqual(action.name, "Next Reel")
        mock_press.assert_called_once_with("down")
        self.assertEqual(len(self.dispatched), 1)

    @patch("watchgesture.core.dispatcher.pyautogui.press")
    def test_dispatch_double_flick(self, mock_press):
        event = GestureEvent(count=2, timestamp=1000.0, trigger_type="timeout")
        action = self.dispatcher.dispatch(event)
        self.assertIsNotNone(action)
        assert action is not None
        self.assertEqual(action.name, "Previous Reel")
        mock_press.assert_called_once_with("up")

    @patch("watchgesture.core.dispatcher.send_win_d")
    def test_dispatch_boss_key(self, mock_win_d):
        event = GestureEvent(count=3, timestamp=1000.0, trigger_type="instant")
        action = self.dispatcher.dispatch(event)
        self.assertIsNotNone(action)
        assert action is not None
        self.assertEqual(action.name, "Boss Key")
        mock_win_d.assert_called_once()

    def test_switch_profile(self):
        media_profile = BUILTIN_PROFILES["media"]
        self.dispatcher.set_profile(media_profile)
        self.assertEqual(self.dispatcher.profile.id, "media")


if __name__ == "__main__":
    unittest.main()

