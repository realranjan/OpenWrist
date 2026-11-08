"""
Telemetry Data Models for WatchGesture.

Encapsulates strongly typed representations of GPS positioning, watch biometrics
(pulse, step count), and bi-directional messaging between phone gateways and desktop HUDs.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Union


@dataclass
class TelemetryPoint:
    """A single GPS and biometric observation received from the phone gateway."""
    lat: float
    lon: float
    accuracy_m: float = 10.0
    bpm: Optional[int] = None
    steps: Optional[int] = None
    message: str = "Auto Sync"
    sos: bool = False
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def maps_url(self) -> str:
        """Returns a direct Google Maps exploration URL for the coordinates."""
        return f"https://www.google.com/maps?q={self.lat:.6f},{self.lon:.6f}"

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the telemetry point into a JSON-friendly dictionary."""
        return {
            "lat": round(self.lat, 6),
            "lon": round(self.lon, 6),
            "acc": round(self.accuracy_m, 1),
            "bpm": self.bpm if self.bpm is not None else "--",
            "steps": self.steps if self.steps is not None else "--",
            "msg": self.message,
            "sos": self.sos,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TelemetryPoint:
        """Deserializes a dictionary into a validated TelemetryPoint instance."""
        lat = float(data.get("lat", 0.0))
        lon = float(data.get("lon", 0.0))
        acc = float(data.get("acc", 10.0))

        # Safe parsing of pulse (BPM)
        bpm_val = data.get("bpm")
        bpm: Optional[int] = None
        if bpm_val not in (None, "--", "", "null"):
            try:
                bpm = int(bpm_val)
            except (ValueError, TypeError):
                bpm = None

        # Safe parsing of steps
        steps_val = data.get("steps")
        steps: Optional[int] = None
        if steps_val not in (None, "--", "", "null"):
            try:
                steps = int(steps_val)
            except (ValueError, TypeError):
                steps = None

        msg = str(data.get("msg", data.get("message", "Auto Sync")))
        sos = bool(data.get("sos", False))

        ts_str = data.get("timestamp")
        if ts_str:
            try:
                ts = datetime.fromisoformat(ts_str)
            except ValueError:
                ts = datetime.now(timezone.utc)
        else:
            ts = datetime.now(timezone.utc)

        return cls(
            lat=lat,
            lon=lon,
            accuracy_m=acc,
            bpm=bpm,
            steps=steps,
            message=msg,
            sos=sos,
            timestamp=ts,
        )

    @classmethod
    def from_json(cls, json_str: str) -> Optional[TelemetryPoint]:
        """Safely parses a raw JSON string into a TelemetryPoint."""
        try:
            data = json.loads(json_str)
            if not isinstance(data, dict):
                return None
            return cls.from_dict(data)
        except Exception:
            return None


@dataclass
class TelemetryConfig:
    """Configuration settings for cloud relay channels and local server port."""
    upstream_topic: str = "watchgesture_telemetry_up"
    downstream_topic: str = "watchgesture_telemetry_down"
    sync_interval_sec: int = 5
    server_port: int = 8765
    server_host: str = "127.0.0.1"
