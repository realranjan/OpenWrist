"""
Unit tests for configuration loading, saving, timing parameters, and profiles.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

# Ensure src/ is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from watchgesture.config import AppConfig, TimingConfig
from watchgesture.profiles.default_profiles import BUILTIN_PROFILES


class TestConfig(unittest.TestCase):
    def test_default_config_values(self):
        config = AppConfig()
        self.assertEqual(config.watch_mac, "AA:BB:CC:DD:EE:FF")
        self.assertEqual(config.active_profile, "reels")
        self.assertEqual(config.timing.gesture_window_sec, 1.00)
        self.assertEqual(config.timing.min_gap_sec, 0.28)
        self.assertEqual(config.timing.lockout_duration_sec, 0.40)

    def test_save_and_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = Path(tmpdir) / "test_config.json"
            config = AppConfig(
                watch_mac="AA:BB:CC:DD:EE:FF",
                device_name="Test Watch",
                active_profile="media",
                timing=TimingConfig(
                    gesture_window_sec=1.5,
                    min_gap_sec=0.35,
                    lockout_duration_sec=0.5,
                ),
            )
            saved = config.save(temp_path)
            self.assertTrue(saved)
            self.assertTrue(temp_path.exists())

            loaded = AppConfig.load(temp_path)
            self.assertEqual(loaded.watch_mac, "AA:BB:CC:DD:EE:FF")
            self.assertEqual(loaded.active_profile, "media")
            self.assertEqual(loaded.timing.gesture_window_sec, 1.5)
            self.assertEqual(loaded.timing.min_gap_sec, 0.35)
            self.assertEqual(loaded.timing.lockout_duration_sec, 0.5)

    def test_get_builtin_profiles(self):
        config = AppConfig(active_profile="reels")
        profile = config.get_profile()
        self.assertEqual(profile.id, "reels")
        self.assertIn(1, profile.actions)
        self.assertIn(2, profile.actions)
        self.assertIn(3, profile.actions)

        # Non-existent profile should fallback safely to reels
        fallback = config.get_profile("non_existent_profile_xyz")
        self.assertEqual(fallback.id, "reels")

    def test_custom_profile_retrieval(self):
        config = AppConfig(
            custom_profiles={
                "gaming": {
                    "name": "Game Controls",
                    "description": "Trigger jump and reload",
                    "actions": {
                        "1": {"name": "Jump", "keys": ["space"], "emoji": "🦘"},
                        "2": {"name": "Reload", "keys": ["r"], "emoji": "🔄"},
                    },
                }
            }
        )
        profile = config.get_profile("gaming")
        self.assertEqual(profile.id, "gaming")
        self.assertEqual(profile.name, "Game Controls")
        self.assertEqual(profile.get_action(1).name, "Jump")
        self.assertEqual(profile.get_action(1).keys, ["space"])
        self.assertEqual(profile.get_action(2).name, "Reload")


if __name__ == "__main__":
    unittest.main()

