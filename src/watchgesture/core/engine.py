"""
Gesture State Machine Engine for WatchGesture.

Processes raw wrist flick events through debounce filters, sliding time windows,
and post-execution lockouts to reliably identify 1-flick, 2-flick, and 3-flick gestures.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Callable, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from watchgesture.config import TimingConfig


@dataclass(frozen=True)
class GestureEvent:
    """Represents a completed gesture ready for execution."""
    count: int
    timestamp: float
    trigger_type: str  # "timeout" or "instant"


class GestureEngine:
    """
    Finite-state machine for collecting and classifying wrist flicks.

    Timing phases:
    1. IDLE: Awaiting first flick.
    2. WINDOW: Accumulating additional flicks up to gesture_window_sec.
       - Discards flicks separated by less than min_gap_sec (wobble debounce).
       - Triggers count 3 immediately without waiting for window expiration.
    3. LOCKOUT: Ignores arm vibrations during post-action cooldown.
    """

    def __init__(
        self,
        gesture_window_sec: float = 1.00,
        min_gap_sec: float = 0.28,
        lockout_duration_sec: float = 0.40,
        on_action: Optional[Callable[[GestureEvent], None]] = None,
        on_flick: Optional[Callable[[int, float], None]] = None,
        on_window_tick: Optional[Callable[[int, float], None]] = None,
    ) -> None:
        self.gesture_window_sec = gesture_window_sec
        self.min_gap_sec = min_gap_sec
        self.lockout_duration_sec = lockout_duration_sec

        self._on_action = on_action
        self._on_flick = on_flick
        self._on_window_tick = on_window_tick

        self._flick_count: int = 0
        self._first_flick_time: float = 0.0
        self._last_flick_time: float = 0.0
        self._lockout_until: float = 0.0
        self._timer_task: Optional[asyncio.Task[None]] = None
        self._running: bool = False

    @property
    def flick_count(self) -> int:
        return self._flick_count

    def is_locked_out(self, now: Optional[float] = None) -> bool:
        """Checks whether the engine is currently in the post-action cooldown period."""
        current_time = time.time() if now is None else now
        return current_time < self._lockout_until

    def update_timing(
        self,
        gesture_window_sec: Optional[float] = None,
        min_gap_sec: Optional[float] = None,
        lockout_duration_sec: Optional[float] = None,
    ) -> None:
        """Dynamically adjusts timing thresholds during runtime calibration."""
        if gesture_window_sec is not None:
            self.gesture_window_sec = max(0.2, float(gesture_window_sec))
        if min_gap_sec is not None:
            self.min_gap_sec = max(0.05, float(min_gap_sec))
        if lockout_duration_sec is not None:
            self.lockout_duration_sec = max(0.1, float(lockout_duration_sec))

    def on_wrist_flick(self, now: Optional[float] = None) -> Optional[GestureEvent]:
        """
        Ingests a wrist flick impulse. Returns a GestureEvent if an instant
        gesture (>= 3 flicks) triggered, otherwise returns None.
        """
        current_time = time.time() if now is None else now

        if current_time < self._lockout_until:
            return None

        if self._flick_count == 0:
            self._flick_count = 1
            self._first_flick_time = current_time
            self._last_flick_time = current_time
            if self._on_flick:
                self._on_flick(1, self.gesture_window_sec)
            return None

        # Subsequent flick in window
        gap = current_time - self._last_flick_time
        elapsed_since_start = current_time - self._first_flick_time

        if gap >= self.min_gap_sec and elapsed_since_start < self.gesture_window_sec:
            self._flick_count += 1
            self._last_flick_time = current_time

            if self._on_flick:
                remaining = max(0.0, self.gesture_window_sec - elapsed_since_start)
                self._on_flick(self._flick_count, remaining)

            # 3 flicks trigger immediately
            if self._flick_count >= 3:
                count = self._flick_count
                self._flick_count = 0
                self._lockout_until = current_time + self.lockout_duration_sec
                event = GestureEvent(count=count, timestamp=current_time, trigger_type="instant")
                if self._on_action:
                    self._on_action(event)
                return event

        return None

    def evaluate_step(self, now: Optional[float] = None) -> Optional[GestureEvent]:
        """
        Periodic evaluation step to trigger actions when the timing window elapses.
        Returns a GestureEvent if the gesture window timed out, or None.
        """
        current_time = time.time() if now is None else now

        if self._flick_count > 0:
            elapsed = current_time - self._first_flick_time
            remaining = max(0.0, self.gesture_window_sec - elapsed)

            if self._on_window_tick:
                self._on_window_tick(self._flick_count, remaining)

            if elapsed >= self.gesture_window_sec:
                count = self._flick_count
                self._flick_count = 0
                self._lockout_until = current_time + self.lockout_duration_sec
                event = GestureEvent(count=count, timestamp=current_time, trigger_type="timeout")

                if self._on_window_tick:
                    self._on_window_tick(0, 0.0)

                if self._on_action:
                    self._on_action(event)

                return event

        return None

    async def run_loop(self, poll_interval: float = 0.02) -> None:
        """Asynchronous background loop for continuous window evaluation."""
        self._running = True
        while self._running:
            self.evaluate_step()
            await asyncio.sleep(poll_interval)

    def stop(self) -> None:
        """Stops the evaluation loop and resets state."""
        self._running = False
        self._flick_count = 0
        if self._timer_task and not self._timer_task.done():
            self._timer_task.cancel()
            self._timer_task = None
