"""
Unit tests for the WatchGesture telemetry data models and relay receiver.
"""

import json
from datetime import datetime, timezone
import unittest

from watchgesture.telemetry.models import TelemetryConfig, TelemetryPoint
from watchgesture.telemetry.server import TelemetryReceiver, WEB_DIR


class TestTelemetryModels(unittest.TestCase):
    """Verifies GPS and biometric data serialization and validation."""

    def test_point_serialization(self) -> None:
        point = TelemetryPoint(
            lat=15.369620,
            lon=75.132854,
            accuracy_m=7.5,
            bpm=76,
            steps=3420,
            message="Test Lock",
            sos=False,
        )
        d = point.to_dict()
        self.assertEqual(d["lat"], 15.36962)
        self.assertEqual(d["lon"], 75.132854)
        self.assertEqual(d["acc"], 7.5)
        self.assertEqual(d["bpm"], 76)
        self.assertEqual(d["steps"], 3420)
        self.assertEqual(d["msg"], "Test Lock")
        self.assertFalse(d["sos"])
        self.assertIn("15.369620,75.132854", point.maps_url)

    def test_point_from_json_valid(self) -> None:
        payload = json.dumps({
            "lat": 12.971598,
            "lon": 77.594562,
            "acc": 5.0,
            "bpm": 82,
            "steps": 1250,
            "msg": "Walking",
            "sos": False,
        })
        point = TelemetryPoint.from_json(payload)
        self.assertIsNotNone(point)
        assert point is not None
        self.assertAlmostEqual(point.lat, 12.971598)
        self.assertAlmostEqual(point.lon, 77.594562)
        self.assertEqual(point.bpm, 82)
        self.assertEqual(point.steps, 1250)
        self.assertEqual(point.message, "Walking")

    def test_point_from_json_null_sensors(self) -> None:
        payload = json.dumps({
            "lat": 28.6139,
            "lon": 77.2090,
            "acc": 12,
            "bpm": "--",
            "steps": "null",
        })
        point = TelemetryPoint.from_json(payload)
        self.assertIsNotNone(point)
        assert point is not None
        self.assertIsNone(point.bpm)
        self.assertIsNone(point.steps)

    def test_point_from_invalid_json(self) -> None:
        self.assertIsNone(TelemetryPoint.from_json("not valid json"))
        self.assertIsNone(TelemetryPoint.from_json("[]"))

    def test_telemetry_config_defaults(self) -> None:
        config = TelemetryConfig()
        self.assertEqual(config.upstream_topic, "watchgesture_telemetry_up")
        self.assertEqual(config.downstream_topic, "watchgesture_telemetry_down")
        self.assertEqual(config.server_port, 8765)

    def test_web_directory_exists(self) -> None:
        self.assertTrue(WEB_DIR.exists())
        self.assertTrue((WEB_DIR / "phone_bridge.html").exists())
        self.assertTrue((WEB_DIR / "live_map.html").exists())


if __name__ == "__main__":
    unittest.main()

