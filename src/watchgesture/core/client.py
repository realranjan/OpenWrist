"""
WatchGesture BLE Client.

Manages the active GATT connection, service discovery, characteristic subscriptions,
keepalive accelerometer heartbeats, and raw event dispatching to the gesture engine.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Callable, Optional, Union

import pyautogui
from bleak import BleakClient
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice

from watchgesture.core.dispatcher import ActionDispatcher
from watchgesture.core.engine import GestureEngine, GestureEvent
from watchgesture.core.protocol import (
    CHAR_NOTIFY_FEE3,
    CHAR_WRITE_FEE2,
    CMD_FIND_MY_PHONE,
    CMD_NOTIFY_PHONE_OPERATION,
    CMD_SWITCH_CAMERA_VIEW,
    OP_DROP_INCOMING_CALL,
    OP_NEXT_SONG,
    OP_PAUSE,
    OP_PLAY,
    OP_PLAY_PAUSE,
    OP_PREV_SONG,
    OP_VOLUME_DOWN,
    OP_VOLUME_UP,
    PHONE_OPERATIONS_MAP,
    PacketReassembler,
    PacketV2,
    is_gesture_notification,
    make_abort_packet,
    make_find_watch_packet,
    make_gsensor_calibration_packet,
    make_keepalive_packet,
    make_screen_message_packet,
)
from watchgesture.core.scanner import find_target_watch

logger = logging.getLogger(__name__)


class WatchGestureClient:
    """High-level client managing smartwatch connection and event processing."""

    def __init__(
        self,
        target_mac: str,
        engine: GestureEngine,
        dispatcher: ActionDispatcher,
        keepalive_interval: float = 6.0,
        fast_rearm: bool = False,
        on_status: Optional[Callable[[str, str], None]] = None,
        on_raw_packet: Optional[Callable[[str, bytes], None]] = None,
    ) -> None:
        self.target_mac = target_mac
        self.engine = engine
        self.dispatcher = dispatcher
        self.keepalive_interval = keepalive_interval
        self.fast_rearm = fast_rearm
        self.on_status = on_status
        self.on_raw_packet = on_raw_packet

        self._client: Optional[BleakClient] = None
        self._keepalive_task: Optional[asyncio.Task[None]] = None
        self._engine_task: Optional[asyncio.Task[None]] = None
        self._running: bool = False
        self._connected: bool = False
        self._reassembler = PacketReassembler()

        # Link engine action trigger to dispatcher
        self.engine._on_action = self._handle_engine_action

    @property
    def is_connected(self) -> bool:
        return self._connected and self._client is not None and self._client.is_connected

    async def buzz_watch(self) -> bool:
        """Sends a command to make the watch buzz/vibrate (Find Watch)."""
        if not self.is_connected or not self._client:
            return False
        try:
            await self._client.write_gatt_char(CHAR_WRITE_FEE2, make_find_watch_packet(), response=False)
            return True
        except Exception as exc:
            logger.warning("Failed to buzz watch: %s", exc)
            return False

    async def calibrate_gsensor(self) -> bool:
        """Sends command to zero and calibrate the watch accelerometer."""
        if not self.is_connected or not self._client:
            return False
        try:
            await self._client.write_gatt_char(CHAR_WRITE_FEE2, make_gsensor_calibration_packet(), response=False)
            return True
        except Exception as exc:
            logger.warning("Failed to calibrate G-sensor: %s", exc)
            return False

    async def send_notification(self, title: str, body: str) -> bool:
        """Displays a text notification directly on the smartwatch screen."""
        if not self.is_connected or not self._client:
            return False
        try:
            packet = make_screen_message_packet(title, body)
            await self._client.write_gatt_char(CHAR_WRITE_FEE2, packet, response=False)
            return True
        except Exception as exc:
            logger.warning("Failed to send notification to watch: %s", exc)
            return False

    def _notify_status(self, status: str, detail: str = "") -> None:
        logger.info("Status -> %s: %s", status, detail)
        if self.on_status:
            self.on_status(status, detail)

    def _handle_engine_action(self, event: GestureEvent) -> None:
        """Triggered by the gesture engine when a gesture is completed."""
        self.dispatcher.dispatch(event)

    async def _keepalive_loop(self) -> None:
        """Keeps the smartwatch accelerometer armed by sending keepalive packets."""
        packet = make_keepalive_packet()
        while self.is_connected:
            try:
                if self._client:
                    await self._client.write_gatt_char(CHAR_WRITE_FEE2, packet, response=False)
            except Exception as exc:
                logger.warning("Heartbeat write failed: %s", exc)
                break
            await asyncio.sleep(self.keepalive_interval)

    async def _notification_callback(self, char: BleakGATTCharacteristic, data: bytearray) -> None:
        """Receives incoming notifications from subscribed BLE characteristics."""
        uuid_str = str(char.uuid).lower()
        raw_bytes = bytes(data)

        if self.on_raw_packet:
            self.on_raw_packet(uuid_str[:8], raw_bytes)

        # Feed byte stream into frame reassembler
        packets = self._reassembler.feed(raw_bytes)
        for packet in packets:
            self._handle_parsed_packet(packet)

    def _handle_parsed_packet(self, packet: PacketV2) -> None:
        """Dispatches fully assembled incoming packets by opcode."""
        # Opcode 102 (0x66): Camera shutter / wrist flick event
        if packet.cmd == CMD_SWITCH_CAMERA_VIEW:
            self.engine.on_wrist_flick()

            # Optional fast-rearm trick (0x53 -> 0x66)
            if self.fast_rearm and self.is_connected and self._client:
                asyncio.create_task(self._fast_rearm_trick())

        # Opcode 103 (0x67): Media & call controls directly from the watch touch screen
        elif packet.cmd == CMD_NOTIFY_PHONE_OPERATION and packet.payload:
            op = packet.payload[0]
            op_name = PHONE_OPERATIONS_MAP.get(op, f"op_{op}")
            logger.info("Watch button pressed: %s (op %d)", op_name, op)

            if op == OP_PLAY_PAUSE:
                pyautogui.press("playpause")
            elif op == OP_PREV_SONG:
                pyautogui.press("prevtrack")
            elif op == OP_NEXT_SONG:
                pyautogui.press("nexttrack")
            elif op == OP_VOLUME_UP:
                pyautogui.press("volumeup")
            elif op == OP_VOLUME_DOWN:
                pyautogui.press("volumedown")

        # Opcode 98 (0x62): "Find Phone" button pressed on the watch
        elif packet.cmd == CMD_FIND_MY_PHONE:
            logger.info("Watch triggered 'Find Phone' alert!")
            # Trigger Boss Key or system focus
            pyautogui.hotkey("win", "d")

    async def _fast_rearm_trick(self) -> None:
        """Quickly cycles 0x53 -> 0x66 to abort watch shutter animation."""
        try:
            if self._client:
                await self._client.write_gatt_char(CHAR_WRITE_FEE2, make_abort_packet(), response=False)
                await asyncio.sleep(0.08)
                await self._client.write_gatt_char(CHAR_WRITE_FEE2, make_keepalive_packet(), response=False)
        except Exception:
            pass

    async def connect_and_run(self, max_reconnect_attempts: int = 0) -> None:
        """
        Connects to the smartwatch and processes gestures until stopped.
        If max_reconnect_attempts > 0, attempts reconnection on link loss.
        """
        self._running = True
        attempts = 0

        while self._running:
            self._notify_status("SCANNING", f"Searching for watch ({self.target_mac})...")
            device = await find_target_watch(self.target_mac, timeout_sec=10.0)

            if not device:
                self._notify_status("NOT_FOUND", "Watch not found. Ensure screen is awake.")
                if max_reconnect_attempts > 0 and attempts < max_reconnect_attempts:
                    attempts += 1
                    await asyncio.sleep(3.0)
                    continue
                break

            self._notify_status("CONNECTING", f"Connecting to {device.name or device.address}...")

            try:
                async with BleakClient(device, timeout=20.0) as client:
                    self._client = client
                    self._connected = True
                    self._notify_status("CONNECTED_ARMED", f"Connected to {device.name or device.address} · Accelerometer Armed")

                    # Start engine background evaluator loop
                    self._engine_task = asyncio.create_task(self.engine.run_loop())
                    # Start 6-second heartbeat
                    self._keepalive_task = asyncio.create_task(self._keepalive_loop())

                    # Initial arm packet
                    await client.write_gatt_char(CHAR_WRITE_FEE2, make_keepalive_packet(), response=False)

                    # Subscribe to all notify/indicate characteristics
                    for service in client.services:
                        for char in service.characteristics:
                            if "notify" in char.properties or "indicate" in char.properties:
                                try:
                                    await client.start_notify(char.uuid, self._notification_callback)
                                except Exception as exc:
                                    logger.debug("Could not subscribe to %s: %s", char.uuid, exc)

                    # Monitor connection state
                    while self._running and client.is_connected:
                        await asyncio.sleep(0.5)

            except Exception as exc:
                logger.error("BLE connection error: %s", exc)
                self._notify_status("ERROR", str(exc))
            finally:
                self._connected = False
                self._client = None
                if self._keepalive_task and not self._keepalive_task.done():
                    self._keepalive_task.cancel()
                if self._engine_task and not self._engine_task.done():
                    self._engine_task.cancel()

            if not self._running:
                break

            if max_reconnect_attempts > 0 and attempts < max_reconnect_attempts:
                attempts += 1
                self._notify_status("RECONNECTING", f"Reconnecting in 3s (attempt {attempts}/{max_reconnect_attempts})...")
                await asyncio.sleep(3.0)
            else:
                break

        self._notify_status("DISCONNECTED", "Controller stopped.")

    def stop(self) -> None:
        """Signals the client and engine to terminate connections cleanly."""
        self._running = False
        self.engine.stop()
        if self._keepalive_task and not self._keepalive_task.done():
            self._keepalive_task.cancel()
        if self._engine_task and not self._engine_task.done():
            self._engine_task.cancel()

