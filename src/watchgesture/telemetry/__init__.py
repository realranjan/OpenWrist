"""
Telemetry and GPS Tracking subsystem for WatchGesture.

Enables zero-tap mobile satellite GPS tracking, smartwatch biometric streaming
(heart rate and steps), and bi-directional notification push over cloud relays.
"""

from watchgesture.telemetry.models import TelemetryConfig, TelemetryPoint
from watchgesture.telemetry.server import TelemetryReceiver, WEB_DIR

__all__ = [
    "TelemetryPoint",
    "TelemetryConfig",
    "TelemetryReceiver",
    "WEB_DIR",
]

