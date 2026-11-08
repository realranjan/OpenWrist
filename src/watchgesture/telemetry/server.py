"""
Telemetry Relay Server and HTTP Host for WatchGesture.

Subscribes to live mobile GPS and watch biometric streams via cloud relays,
provides bi-directional push messaging to the watch display, and serves
the responsive mobile bridge and desktop live map HUD locally.
"""

from __future__ import annotations

import http.server
import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path
from typing import Callable, Optional

from watchgesture.telemetry.models import TelemetryConfig, TelemetryPoint

logger = logging.getLogger(__name__)

WEB_DIR = Path(__file__).parent / "web"


class TelemetryHTTPHandler(http.server.SimpleHTTPRequestHandler):
    """Serves the static web assets from the telemetry/web directory."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def log_message(self, format: str, *args) -> None:
        # Suppress noisy standard HTTP access logs in console
        logger.debug("HTTP %s", format % args)


class TelemetryReceiver:
    """
    Subscribes to incoming mobile telemetry streams and coordinates HUD updates
    and bi-directional watch screen messaging.
    """

    def __init__(
        self,
        config: Optional[TelemetryConfig] = None,
        on_point_received: Optional[Callable[[TelemetryPoint], None]] = None,
    ) -> None:
        self.config = config or TelemetryConfig()
        self.on_point_received = on_point_received
        self._running: bool = False
        self._thread: Optional[threading.Thread] = None
        self._http_server: Optional[http.server.ThreadingHTTPServer] = None
        self._http_thread: Optional[threading.Thread] = None

    def start_listener(self) -> None:
        """Starts background listener streaming incoming JSON telemetry packets."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        logger.info("Telemetry receiver listening on upstream topic: %s", self.config.upstream_topic)

    def stop(self) -> None:
        """Stops background stream listener and local HTTP server."""
        self._running = False
        if self._http_server:
            try:
                self._http_server.shutdown()
            except Exception:
                pass

    def send_message_to_watch(self, message: str) -> bool:
        """
        Dispatches a text message to the phone bridge via downstream topic,
        which immediately pushes Opcode 0x41 to the watch screen.
        """
        url = f"https://ntfy.sh/{self.config.downstream_topic}"
        data = message.encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "User-Agent": "WatchGesture/1.0",
                "Title": "PC Message",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                success = 200 <= resp.status < 300
                if success:
                    logger.info("Dispatched message to watch screen: '%s'", message)
                return success
        except Exception as exc:
            logger.error("Failed to send message to watch: %s", exc)
            return False

    def start_http_server(self, open_browser: bool = True) -> int:
        """Starts a local HTTP server to host the live map and phone bridge."""
        server_address = (self.config.server_host, self.config.server_port)
        try:
            self._http_server = http.server.ThreadingHTTPServer(server_address, TelemetryHTTPHandler)
        except OSError:
            # Fall back to an ephemeral free port if default is bound
            self._http_server = http.server.ThreadingHTTPServer((self.config.server_host, 0), TelemetryHTTPHandler)

        port = self._http_server.server_port
        self._http_thread = threading.Thread(target=self._http_server.serve_forever, daemon=True)
        self._http_thread.start()

        map_url = f"http://localhost:{port}/live_map.html?up={self.config.upstream_topic}&down={self.config.downstream_topic}"
        logger.info("Telemetry Web Server running at: http://localhost:%d", port)

        if open_browser:
            webbrowser.open(map_url)

        return port

    def _listen_loop(self) -> None:
        """Continuous streaming read loop using standard library urllib."""
        stream_url = f"https://ntfy.sh/{self.config.upstream_topic}/json"

        while self._running:
            try:
                req = urllib.request.Request(
                    stream_url,
                    headers={"User-Agent": "WatchGesture-Telemetry/1.0"},
                )
                with urllib.request.urlopen(req, timeout=65.0) as resp:
                    for raw_line in resp:
                        if not self._running:
                            break
                        if not raw_line:
                            continue
                        line_str = raw_line.decode("utf-8", errors="replace").strip()
                        if not line_str:
                            continue

                        try:
                            envelope = json.loads(line_str)
                            if envelope.get("event") != "message":
                                continue
                            msg_payload = envelope.get("message", "")
                            point = TelemetryPoint.from_json(msg_payload)
                            if point and self.on_point_received:
                                self.on_point_received(point)
                        except Exception as parse_err:
                            logger.debug("Telemetry parse skipped: %s", parse_err)

            except Exception as stream_err:
                if self._running:
                    logger.debug("Telemetry stream reconnecting in 2s: %s", stream_err)
                    time.sleep(2.0)
