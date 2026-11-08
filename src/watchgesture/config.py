"""
Configuration and Profile Management for WatchGesture.

Handles loading, validating, and persisting runtime options, device addresses,
timing calibrations, and input profile mappings.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

from watchgesture.profiles.default_profiles import BUILTIN_PROFILES, ActionItem, GestureProfile


CONFIG_DIR = Path.home() / ".watchgesture"
CONFIG_FILE = CONFIG_DIR / "config.json"
FALLBACK_CONFIG_FILE = Path("config.json")


@dataclass
class TimingConfig:
    """Configurable timing thresholds for gesture recognition."""
    gesture_window_sec: float = 1.00
    min_gap_sec: float = 0.28
    lockout_duration_sec: float = 0.40
    keepalive_interval_sec: float = 6.0


@dataclass
class AppConfig:
    """Master application configuration."""
    watch_mac: str = "CE:E6:79:A9:BE:3B"
    device_name: str = "Fire-Boltt 184"
    active_profile: str = "reels"
    fast_rearm: bool = False
    timing: TimingConfig = field(default_factory=TimingConfig)
    custom_profiles: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def get_config_path(cls) -> Path:
        """Determines the appropriate configuration file path."""
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            return CONFIG_FILE
        except OSError:
            return FALLBACK_CONFIG_FILE

    @classmethod
    def load(cls, path: Optional[Path] = None) -> AppConfig:
        """Loads configuration from JSON file or returns safe defaults."""
        target_path = path or cls.get_config_path()
        if not target_path.exists() and FALLBACK_CONFIG_FILE.exists():
            target_path = FALLBACK_CONFIG_FILE

        if not target_path.exists():
            instance = cls()
            instance.save(target_path)
            return instance

        try:
            with open(target_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            timing_data = data.get("timing", {})
            timing = TimingConfig(
                gesture_window_sec=float(timing_data.get("gesture_window_sec", 1.00)),
                min_gap_sec=float(timing_data.get("min_gap_sec", 0.28)),
                lockout_duration_sec=float(timing_data.get("lockout_duration_sec", 0.40)),
                keepalive_interval_sec=float(timing_data.get("keepalive_interval_sec", 6.0)),
            )

            return cls(
                watch_mac=str(data.get("watch_mac", "CE:E6:79:A9:BE:3B")),
                device_name=str(data.get("device_name", "Fire-Boltt 184")),
                active_profile=str(data.get("active_profile", "reels")),
                fast_rearm=bool(data.get("fast_rearm", False)),
                timing=timing,
                custom_profiles=dict(data.get("custom_profiles", {})),
            )
        except Exception:
            return cls()

    def save(self, path: Optional[Path] = None) -> bool:
        """Serializes current configuration to disk."""
        target_path = path or self.get_config_path()
        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "watch_mac": self.watch_mac,
                "device_name": self.device_name,
                "active_profile": self.active_profile,
                "fast_rearm": self.fast_rearm,
                "timing": asdict(self.timing),
                "custom_profiles": self.custom_profiles,
            }
            with open(target_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            return True
        except OSError:
            return False

    def get_profile(self, profile_id: Optional[str] = None) -> GestureProfile:
        """Retrieves active or requested GestureProfile."""
        pid = profile_id or self.active_profile
        if pid in BUILTIN_PROFILES:
            return BUILTIN_PROFILES[pid]

        if pid in self.custom_profiles:
            custom_data = self.custom_profiles[pid]
            actions: Dict[int, ActionItem] = {}
            for count_str, action_dict in custom_data.get("actions", {}).items():
                count = int(count_str)
                actions[count] = ActionItem(
                    count=count,
                    name=action_dict.get("name", f"Action {count}"),
                    description=action_dict.get("description", ""),
                    emoji=action_dict.get("emoji", "⚡"),
                    action_type=action_dict.get("action_type", "key"),
                    keys=list(action_dict.get("keys", ["down"])),
                )
            return GestureProfile(
                id=pid,
                name=custom_data.get("name", pid),
                description=custom_data.get("description", "Custom user profile"),
                actions=actions,
            )

        return BUILTIN_PROFILES["reels"]

