"""
Unit tests for the Gesture Engine state machine, timing windows, debounce, and lockouts.
"""

import sys
import unittest
from pathlib import Path

# Ensure src/ is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from watchgesture.core.engine import GestureEngine, GestureEvent


class TestGestureEngine(unittest.TestCase):
    def setUp(self):
        self.dispatched_events = []
        self.flick_reports = []

        def on_action(event: GestureEvent):
            self.dispatched_events.append(event)

        def on_flick(count: int, remaining: float):
            self.flick_reports.append((count, remaining))

        self.engine = GestureEngine(
            gesture_window_sec=1.00,
            min_gap_sec=0.28,
            lockout_duration_sec=0.40,
            on_action=on_action,
            on_flick=on_flick,
        )

    def test_single_flick_timeout(self):
        t0 = 1000.0
        # Flick 1 occurs
        res = self.engine.on_wrist_flick(now=t0)
        self.assertIsNone(res)
        self.assertEqual(self.engine.flick_count, 1)

        # Mid-window tick (0.5s later) -> should not trigger yet
        res_mid = self.engine.evaluate_step(now=t0 + 0.5)
        self.assertIsNone(res_mid)
        self.assertEqual(len(self.dispatched_events), 0)

        # Window expires at 1.01s
        res_exp = self.engine.evaluate_step(now=t0 + 1.01)
        self.assertIsNotNone(res_exp)
        assert res_exp is not None
        self.assertEqual(res_exp.count, 1)
        self.assertEqual(res_exp.trigger_type, "timeout")
        self.assertEqual(len(self.dispatched_events), 1)
        self.assertEqual(self.engine.flick_count, 0)

    def test_double_flick_timeout(self):
        t0 = 1000.0
        # Flick 1
        self.engine.on_wrist_flick(now=t0)
        # Flick 2 at t0 + 0.35s (> min_gap_sec 0.28s)
        self.engine.on_wrist_flick(now=t0 + 0.35)
        self.assertEqual(self.engine.flick_count, 2)

        # Window expires at t0 + 1.05s
        res = self.engine.evaluate_step(now=t0 + 1.05)
        self.assertIsNotNone(res)
        assert res is not None
        self.assertEqual(res.count, 2)
        self.assertEqual(self.dispatched_events[0].count, 2)

    def test_triple_flick_instant_trigger(self):
        t0 = 1000.0
        # Flick 1
        self.engine.on_wrist_flick(now=t0)
        # Flick 2 at 0.30s
        self.engine.on_wrist_flick(now=t0 + 0.30)
        # Flick 3 at 0.60s -> should trigger instantly!
        res = self.engine.on_wrist_flick(now=t0 + 0.60)
        self.assertIsNotNone(res)
        assert res is not None
        self.assertEqual(res.count, 3)
        self.assertEqual(res.trigger_type, "instant")
        self.assertEqual(len(self.dispatched_events), 1)
        self.assertEqual(self.engine.flick_count, 0)
        # Should now be in lockout at t0 + 0.70
        self.assertTrue(self.engine.is_locked_out(now=t0 + 0.70))
        # Lockout expires after t0 + 1.00
        self.assertFalse(self.engine.is_locked_out(now=t0 + 1.05))

    def test_debounce_gap_filter(self):
        t0 = 1000.0
        # Flick 1
        self.engine.on_wrist_flick(now=t0)
        # Rapid bounce at t0 + 0.10s (< min_gap 0.28s) -> MUST BE IGNORED
        self.engine.on_wrist_flick(now=t0 + 0.10)
        self.assertEqual(self.engine.flick_count, 1)

        # Valid flick at t0 + 0.32s
        self.engine.on_wrist_flick(now=t0 + 0.32)
        self.assertEqual(self.engine.flick_count, 2)

    def test_post_action_lockout(self):
        t0 = 1000.0
        self.engine.on_wrist_flick(now=t0)
        self.engine.on_wrist_flick(now=t0 + 0.30)
        self.engine.on_wrist_flick(now=t0 + 0.60)  # Triggers instant 3-flick action

        # Lockout is set to t0 + 0.60 + 0.40 = 1001.00
        # Arm vibration during settlement at 1000.80s
        res_during_lockout = self.engine.on_wrist_flick(now=1000.80)
        self.assertIsNone(res_during_lockout)
        self.assertEqual(self.engine.flick_count, 0)

        # After lockout clears at 1001.05s
        self.engine.on_wrist_flick(now=1001.05)
        self.assertEqual(self.engine.flick_count, 1)


if __name__ == "__main__":
    unittest.main()
