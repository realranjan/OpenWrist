"""
WatchGesture Desktop GUI.

A high-performance, polished Tkinter application built with a modern
dark-mode design system, live sensor telemetry, device pairing,
real-time gesture radar visualization, and profile switching.
"""

from __future__ import annotations

import asyncio
import queue
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Any, Dict, List, Optional, Tuple

from watchgesture.config import AppConfig
from watchgesture.core.client import WatchGestureClient
from watchgesture.core.dispatcher import ActionDispatcher
from watchgesture.core.engine import GestureEngine, GestureEvent
from watchgesture.core.protocol import is_gesture_notification
from watchgesture.core.scanner import scan_for_devices
from watchgesture.profiles.default_profiles import BUILTIN_PROFILES, ActionItem, GestureProfile

# --- Design Tokens (Linear/Stripe Dark Palette) ---
BG_DARK = "#0d1117"
BG_PANEL = "#161b22"
BG_CARD = "#21262d"
BG_INPUT = "#0d1117"
BORDER = "#30363d"
BORDER_FOCUS = "#58a6ff"

TEXT_PRIMARY = "#f0f6fc"
TEXT_SECONDARY = "#8b949e"
TEXT_MUTED = "#6e7681"

ACCENT_BLUE = "#58a6ff"
ACCENT_GREEN = "#3fb950"
ACCENT_AMBER = "#d29922"
ACCENT_RED = "#f85149"
ACCENT_PURPLE = "#bc8cff"

FONT_FAMILY = "Segoe UI" if sys.platform == "win32" else "Helvetica"


class WatchGestureApp:
    """Main Application Controller for the WatchGesture GUI."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("WatchGesture — Smartwatch Controller")
        self.root.geometry("820x760")
        self.root.minsize(720, 640)
        self.root.configure(bg=BG_DARK)

        self.config = AppConfig.load()
        self.ui_queue: queue.Queue[Tuple[str, Any]] = queue.Queue()

        self._ble_thread: Optional[threading.Thread] = None
        self._ble_loop: Optional[asyncio.AbstractEventLoop] = None
        self._client: Optional[WatchGestureClient] = None
        self._is_connecting: bool = False
        self._is_connected: bool = False

        self._setup_styles()
        self._build_ui()
        self._start_queue_poller()

        # Update initial profile state
        self._on_profile_selected(self.config.active_profile)

    def _setup_styles(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")

        style.configure(".", background=BG_DARK, foreground=TEXT_PRIMARY, font=(FONT_FAMILY, 10))
        style.configure("TFrame", background=BG_DARK)
        style.configure("Card.TFrame", background=BG_PANEL, relief="flat")

        style.configure(
            "TCombobox",
            fieldbackground=BG_INPUT,
            background=BG_CARD,
            foreground=TEXT_PRIMARY,
            arrowcolor=TEXT_PRIMARY,
            bordercolor=BORDER,
        )

        style.configure(
            "Horizontal.TProgressbar",
            troughcolor=BG_CARD,
            background=ACCENT_BLUE,
            thickness=6,
        )

    def _build_ui(self) -> None:
        # Main container with padding
        main_frame = tk.Frame(self.root, bg=BG_DARK)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=24, pady=20)

        # 1. Header with title and connection status badge
        header_frame = tk.Frame(main_frame, bg=BG_DARK)
        header_frame.pack(fill=tk.X, pady=(0, 16))

        title_label = tk.Label(
            header_frame,
            text="⌚ WatchGesture",
            font=(FONT_FAMILY, 18, "bold"),
            fg=TEXT_PRIMARY,
            bg=BG_DARK,
        )
        title_label.pack(side=tk.LEFT)

        subtitle_label = tk.Label(
            header_frame,
            text="v1.0.0 · BLE Smartwatch Wrist Control",
            font=(FONT_FAMILY, 10),
            fg=TEXT_MUTED,
            bg=BG_DARK,
        )
        subtitle_label.pack(side=tk.LEFT, padx=(10, 0), pady=(4, 0))

        # Status badge container
        self.status_badge = tk.Label(
            header_frame,
            text="● DISCONNECTED",
            font=(FONT_FAMILY, 9, "bold"),
            fg=TEXT_MUTED,
            bg=BG_CARD,
            padx=12,
            pady=4,
            relief="flat",
        )
        self.status_badge.pack(side=tk.RIGHT)

        # 2. Connection Control Card
        conn_card = tk.Frame(main_frame, bg=BG_PANEL, highlightbackground=BORDER, highlightthickness=1)
        conn_card.pack(fill=tk.X, pady=(0, 14), ipadx=16, ipady=12)

        conn_top = tk.Frame(conn_card, bg=BG_PANEL)
        conn_top.pack(fill=tk.X)

        mac_label = tk.Label(conn_top, text="TARGET WATCH MAC:", font=(FONT_FAMILY, 9, "bold"), fg=TEXT_SECONDARY, bg=BG_PANEL)
        mac_label.pack(side=tk.LEFT, padx=(0, 10))

        self.mac_entry = tk.Entry(
            conn_top,
            font=(FONT_FAMILY, 10, "bold"),
            fg=TEXT_PRIMARY,
            bg=BG_INPUT,
            insertbackground=TEXT_PRIMARY,
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=BORDER_FOCUS,
            width=22,
        )
        self.mac_entry.insert(0, self.config.watch_mac)
        self.mac_entry.pack(side=tk.LEFT, padx=(0, 10))

        self.btn_scan = tk.Button(
            conn_top,
            text="🔍 Scan Nearby",
            font=(FONT_FAMILY, 9, "bold"),
            fg=TEXT_PRIMARY,
            bg=BG_CARD,
            activebackground=BORDER,
            activeforeground=TEXT_PRIMARY,
            relief="flat",
            padx=12,
            pady=4,
            cursor="hand2",
            command=self._handle_scan_click,
        )
        self.btn_scan.pack(side=tk.LEFT, padx=(0, 10))

        self.btn_connect = tk.Button(
            conn_top,
            text="⚡ Connect Watch",
            font=(FONT_FAMILY, 10, "bold"),
            fg="#ffffff",
            bg=ACCENT_BLUE,
            activebackground="#4387d8",
            activeforeground="#ffffff",
            relief="flat",
            padx=16,
            pady=4,
            cursor="hand2",
            command=self._handle_toggle_connect,
        )
        self.btn_connect.pack(side=tk.RIGHT)

        # Hardware Actions Bar (Buzz / Zero Accelerometer)
        conn_actions = tk.Frame(conn_card, bg=BG_PANEL)
        conn_actions.pack(fill=tk.X, pady=(10, 0))

        self.btn_buzz = tk.Button(
            conn_actions,
            text="🔔 Buzz Watch",
            font=(FONT_FAMILY, 8, "bold"),
            fg=TEXT_MUTED,
            bg=BG_CARD,
            activebackground=BORDER,
            activeforeground=TEXT_PRIMARY,
            relief="flat",
            padx=10,
            pady=3,
            cursor="hand2",
            state="disabled",
            command=self._handle_buzz_watch,
        )
        self.btn_buzz.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_zero_accel = tk.Button(
            conn_actions,
            text="🎯 Calibrate Accelerometer",
            font=(FONT_FAMILY, 8, "bold"),
            fg=TEXT_MUTED,
            bg=BG_CARD,
            activebackground=BORDER,
            activeforeground=TEXT_PRIMARY,
            relief="flat",
            padx=10,
            pady=3,
            cursor="hand2",
            state="disabled",
            command=self._handle_zero_accel,
        )
        self.btn_zero_accel.pack(side=tk.LEFT)

        # 3. Profile & Mapping Card
        profile_card = tk.Frame(main_frame, bg=BG_PANEL, highlightbackground=BORDER, highlightthickness=1)
        profile_card.pack(fill=tk.X, pady=(0, 14), ipadx=16, ipady=12)

        prof_header = tk.Frame(profile_card, bg=BG_PANEL)
        prof_header.pack(fill=tk.X, pady=(0, 10))

        prof_title = tk.Label(prof_header, text="ACTIVE GESTURE PROFILE:", font=(FONT_FAMILY, 9, "bold"), fg=TEXT_SECONDARY, bg=BG_PANEL)
        prof_title.pack(side=tk.LEFT)

        self.profile_combo = ttk.Combobox(
            prof_header,
            values=[p.name for p in BUILTIN_PROFILES.values()],
            state="readonly",
            width=26,
        )
        current_prof = BUILTIN_PROFILES.get(self.config.active_profile, BUILTIN_PROFILES["reels"])
        self.profile_combo.set(current_prof.name)
        self.profile_combo.bind("<<ComboboxSelected>>", self._handle_profile_change)
        self.profile_combo.pack(side=tk.LEFT, padx=(10, 0))

        # Tiles grid for 1 flick, 2 flicks, 3 flicks
        self.tiles_frame = tk.Frame(profile_card, bg=BG_PANEL)
        self.tiles_frame.pack(fill=tk.X)

        self.tiles: Dict[int, Dict[str, Any]] = {}
        for count in (1, 2, 3):
            tile = tk.Frame(self.tiles_frame, bg=BG_CARD, highlightbackground=BORDER, highlightthickness=1)
            tile.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, ipadx=10, ipady=8)

            lbl_flick = tk.Label(tile, text=f"{count} FLICK{'S' if count > 1 else ''}", font=(FONT_FAMILY, 8, "bold"), fg=TEXT_MUTED, bg=BG_CARD)
            lbl_flick.pack(anchor="w")

            lbl_action = tk.Label(tile, text="--", font=(FONT_FAMILY, 11, "bold"), fg=TEXT_PRIMARY, bg=BG_CARD)
            lbl_action.pack(anchor="w", pady=(2, 0))

            lbl_sub = tk.Label(tile, text="--", font=(FONT_FAMILY, 8), fg=TEXT_SECONDARY, bg=BG_CARD)
            lbl_sub.pack(anchor="w")

            self.tiles[count] = {"frame": tile, "action": lbl_action, "sub": lbl_sub}

        # 4. Real-time Telemetry & Gesture Radar Card
        radar_card = tk.Frame(main_frame, bg=BG_PANEL, highlightbackground=BORDER, highlightthickness=1)
        radar_card.pack(fill=tk.X, pady=(0, 14), ipadx=16, ipady=12)

        radar_header = tk.Frame(radar_card, bg=BG_PANEL)
        radar_header.pack(fill=tk.X, pady=(0, 8))

        radar_title = tk.Label(radar_header, text="GESTURE RADAR & TIMING WINDOW:", font=(FONT_FAMILY, 9, "bold"), fg=TEXT_SECONDARY, bg=BG_PANEL)
        radar_title.pack(side=tk.LEFT)

        self.lbl_radar_state = tk.Label(radar_header, text="Idle", font=(FONT_FAMILY, 9), fg=TEXT_MUTED, bg=BG_PANEL)
        self.lbl_radar_state.pack(side=tk.RIGHT)

        # Progress bar representing the sliding gesture window countdown
        self.progress_var = tk.DoubleVar(value=0.0)
        self.progress_bar = ttk.Progressbar(
            radar_card,
            variable=self.progress_var,
            maximum=100.0,
            style="Horizontal.TProgressbar",
        )
        self.progress_bar.pack(fill=tk.X, pady=(0, 8))

        # Recent action banner
        self.banner_action = tk.Label(
            radar_card,
            text="Waiting for wrist flicks... (Snap your wrist while looking at watch screen)",
            font=(FONT_FAMILY, 10),
            fg=TEXT_SECONDARY,
            bg=BG_CARD,
            pady=6,
            highlightbackground=BORDER,
            highlightthickness=1,
        )
        self.banner_action.pack(fill=tk.X)

        # 5. Timing Calibration Card (Live Tuner)
        calib_card = tk.Frame(main_frame, bg=BG_PANEL, highlightbackground=BORDER, highlightthickness=1)
        calib_card.pack(fill=tk.X, pady=(0, 14), ipadx=16, ipady=10)

        calib_top = tk.Frame(calib_card, bg=BG_PANEL)
        calib_top.pack(fill=tk.X, pady=(0, 8))

        calib_title = tk.Label(
            calib_top,
            text="⚙️ TIMING CALIBRATION & REBOUND FILTERS:",
            font=(FONT_FAMILY, 9, "bold"),
            fg=TEXT_SECONDARY,
            bg=BG_PANEL,
        )
        calib_title.pack(side=tk.LEFT)

        btn_save_calib = tk.Button(
            calib_top,
            text="Save & Apply",
            font=(FONT_FAMILY, 8, "bold"),
            fg=TEXT_PRIMARY,
            bg=BG_CARD,
            activebackground=BORDER,
            activeforeground=TEXT_PRIMARY,
            relief="flat",
            padx=10,
            pady=2,
            cursor="hand2",
            command=self._handle_save_calibration,
        )
        btn_save_calib.pack(side=tk.RIGHT)

        inputs_frame = tk.Frame(calib_card, bg=BG_PANEL)
        inputs_frame.pack(fill=tk.X)

        # Field 1: Window Duration
        f1 = tk.Frame(inputs_frame, bg=BG_PANEL)
        f1.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        tk.Label(f1, text="Window (sec):", font=(FONT_FAMILY, 8), fg=TEXT_MUTED, bg=BG_PANEL).pack(anchor="w")
        self.entry_window = tk.Entry(f1, font=(FONT_FAMILY, 9), bg=BG_INPUT, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY, highlightthickness=1, highlightbackground=BORDER, highlightcolor=BORDER_FOCUS, width=8)
        self.entry_window.insert(0, f"{self.config.timing.gesture_window_sec:.2f}")
        self.entry_window.pack(fill=tk.X, pady=(2, 0))

        # Field 2: Min Gap Debounce
        f2 = tk.Frame(inputs_frame, bg=BG_PANEL)
        f2.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        tk.Label(f2, text="Min Gap (sec):", font=(FONT_FAMILY, 8), fg=TEXT_MUTED, bg=BG_PANEL).pack(anchor="w")
        self.entry_gap = tk.Entry(f2, font=(FONT_FAMILY, 9), bg=BG_INPUT, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY, highlightthickness=1, highlightbackground=BORDER, highlightcolor=BORDER_FOCUS, width=8)
        self.entry_gap.insert(0, f"{self.config.timing.min_gap_sec:.2f}")
        self.entry_gap.pack(fill=tk.X, pady=(2, 0))

        # Field 3: Lockout Cooldown
        f3 = tk.Frame(inputs_frame, bg=BG_PANEL)
        f3.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        tk.Label(f3, text="Lockout (sec):", font=(FONT_FAMILY, 8), fg=TEXT_MUTED, bg=BG_PANEL).pack(anchor="w")
        self.entry_lockout = tk.Entry(f3, font=(FONT_FAMILY, 9), bg=BG_INPUT, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY, highlightthickness=1, highlightbackground=BORDER, highlightcolor=BORDER_FOCUS, width=8)
        self.entry_lockout.insert(0, f"{self.config.timing.lockout_duration_sec:.2f}")
        self.entry_lockout.pack(fill=tk.X, pady=(2, 0))

        # Field 4: Fast Rearm Toggle
        f4 = tk.Frame(inputs_frame, bg=BG_PANEL)
        f4.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        self.fast_rearm_var = tk.BooleanVar(value=self.config.fast_rearm)
        chk_rearm = tk.Checkbutton(
            f4,
            text="Fast Rearm (0x53)",
            variable=self.fast_rearm_var,
            font=(FONT_FAMILY, 8),
            fg=TEXT_SECONDARY,
            bg=BG_PANEL,
            activebackground=BG_PANEL,
            activeforeground=TEXT_PRIMARY,
            selectcolor=BG_CARD,
        )
        chk_rearm.pack(anchor="w", pady=(14, 0))

        # 6. Live Activity Console
        console_card = tk.Frame(main_frame, bg=BG_PANEL, highlightbackground=BORDER, highlightthickness=1)
        console_card.pack(fill=tk.BOTH, expand=True, ipadx=16, ipady=12)

        cons_header = tk.Frame(console_card, bg=BG_PANEL)
        cons_header.pack(fill=tk.X, pady=(0, 6))

        cons_title = tk.Label(cons_header, text="LIVE EVENT LOG:", font=(FONT_FAMILY, 9, "bold"), fg=TEXT_SECONDARY, bg=BG_PANEL)
        cons_title.pack(side=tk.LEFT)

        btn_clear = tk.Button(
            cons_header,
            text="Clear",
            font=(FONT_FAMILY, 8),
            fg=TEXT_MUTED,
            bg=BG_CARD,
            relief="flat",
            cursor="hand2",
            command=self._clear_log,
        )
        btn_clear.pack(side=tk.RIGHT)

        self.log_text = tk.Text(
            console_card,
            bg=BG_INPUT,
            fg=TEXT_PRIMARY,
            insertbackground=TEXT_PRIMARY,
            relief="flat",
            font=("Consolas", 9),
            height=8,
            wrap=tk.WORD,
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def _log(self, message: str) -> None:
        """Appends a line to the GUI console."""
        now_str = time.strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{now_str}] {message}\n")
        self.log_text.see(tk.END)

    def _clear_log(self) -> None:
        self.log_text.delete("1.0", tk.END)

    def _update_status(self, status: str, detail: str = "") -> None:
        """Updates the status badge color and text."""
        badge_configs = {
            "DISCONNECTED": ("● DISCONNECTED", TEXT_MUTED, BG_CARD),
            "SCANNING": ("● SCANNING...", ACCENT_AMBER, BG_CARD),
            "CONNECTING": ("● CONNECTING...", ACCENT_BLUE, BG_CARD),
            "CONNECTED_ARMED": ("● ARMED & READY", ACCENT_GREEN, "#1c3326"),
            "RECONNECTING": ("● RECONNECTING...", ACCENT_AMBER, BG_CARD),
            "ERROR": ("● ERROR", ACCENT_RED, "#381e22"),
        }
        text, fg, bg = badge_configs.get(status, ("● " + status, TEXT_PRIMARY, BG_CARD))
        self.status_badge.config(text=text, fg=fg, bg=bg)
        if detail:
            self._log(f"Status: {detail}")

    def _on_profile_selected(self, profile_id: str) -> None:
        """Updates the 3 gesture display tiles based on selected profile."""
        profile = self.config.get_profile(profile_id)
        for count in (1, 2, 3):
            action = profile.get_action(count)
            if action:
                keys_str = " + ".join(action.keys)
                self.tiles[count]["action"].config(text=f"{action.emoji} {action.name}")
                self.tiles[count]["sub"].config(text=f"{action.description} · [{keys_str}]")
            else:
                self.tiles[count]["action"].config(text="--")
                self.tiles[count]["sub"].config(text="Unmapped")

    def _handle_save_calibration(self) -> None:
        """Parses and applies live timing threshold calibration."""
        try:
            window = float(self.entry_window.get().strip())
            gap = float(self.entry_gap.get().strip())
            lockout = float(self.entry_lockout.get().strip())
            fast_rearm = bool(self.fast_rearm_var.get())

            if window < 0.2 or gap < 0.05 or lockout < 0.05:
                messagebox.showwarning("Invalid Values", "Values are too small. Window >= 0.2s, Gap >= 0.05s, Lockout >= 0.05s.")
                return

            self.config.timing.gesture_window_sec = window
            self.config.timing.min_gap_sec = gap
            self.config.timing.lockout_duration_sec = lockout
            self.config.fast_rearm = fast_rearm
            self.config.save()

            if self._client:
                self._client.fast_rearm = fast_rearm
                self._client.engine.update_timing(
                    gesture_window_sec=window,
                    min_gap_sec=gap,
                    lockout_duration_sec=lockout,
                )

            self._log(f"Calibration applied: Window={window:.2f}s | Gap={gap:.2f}s | Lockout={lockout:.2f}s | FastRearm={fast_rearm}")
        except ValueError:
            messagebox.showerror("Format Error", "Please enter valid floating-point numbers for timing parameters.")

    def _handle_profile_change(self, event: Any = None) -> None:
        selected_name = self.profile_combo.get()
        for pid, p in BUILTIN_PROFILES.items():
            if p.name == selected_name:
                self.config.active_profile = pid
                self.config.save()
                self._on_profile_selected(pid)
                if self._client:
                    self._client.dispatcher.set_profile(p)
                self._log(f"Switched profile to: {p.name}")
                break

    def _handle_toggle_connect(self) -> None:
        if self._is_connected or self._is_connecting:
            self._disconnect_watch()
        else:
            self._connect_watch()

    def _connect_watch(self) -> None:
        target_mac = self.mac_entry.get().strip()
        if not target_mac:
            messagebox.showwarning("Missing MAC Address", "Please enter or scan for your watch Bluetooth address.")
            return

        self.config.watch_mac = target_mac
        self.config.save()

        self._is_connecting = True
        self.btn_connect.config(text="Connecting...", state="disabled", bg=BG_CARD)
        self.btn_scan.config(state="disabled")

        self._ble_thread = threading.Thread(target=self._run_ble_worker, args=(target_mac,), daemon=True)
        self._ble_thread.start()

    def _disconnect_watch(self) -> None:
        if self._client:
            self._client.stop()
        self._is_connected = False
        self._is_connecting = False
        self.btn_connect.config(text="⚡ Connect Watch", state="normal", bg=ACCENT_BLUE)
        self.btn_scan.config(state="normal")
        self._update_status("DISCONNECTED", "Disconnected from smartwatch.")

    def _run_ble_worker(self, target_mac: str) -> None:
        """Background thread hosting the asyncio BLE connection."""
        self._ble_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._ble_loop)

        profile = self.config.get_profile()

        def on_action_dispatched(action: ActionItem, now_str: str) -> None:
            self.ui_queue.put(("action", (action, now_str)))

        dispatcher = ActionDispatcher(profile=profile, on_action_dispatched=on_action_dispatched)

        def on_flick(count: int, time_left: float) -> None:
            self.ui_queue.put(("flick", (count, time_left)))

        def on_window_tick(count: int, remaining: float) -> None:
            self.ui_queue.put(("tick", (count, remaining)))

        engine = GestureEngine(
            gesture_window_sec=self.config.timing.gesture_window_sec,
            min_gap_sec=self.config.timing.min_gap_sec,
            lockout_duration_sec=self.config.timing.lockout_duration_sec,
            on_flick=on_flick,
            on_window_tick=on_window_tick,
        )

        def on_status(status: str, detail: str) -> None:
            self.ui_queue.put(("status", (status, detail)))

        client = WatchGestureClient(
            target_mac=target_mac,
            engine=engine,
            dispatcher=dispatcher,
            fast_rearm=self.config.fast_rearm,
            on_status=on_status,
        )
        self._client = client

        try:
            self._ble_loop.run_until_complete(client.connect_and_run(max_reconnect_attempts=0))
        except Exception as exc:
            self.ui_queue.put(("status", ("ERROR", str(exc))))
        finally:
            self._ble_loop.close()

    def _handle_scan_click(self) -> None:
        self.btn_scan.config(state="disabled", text="Scanning...")
        self._update_status("SCANNING", "Scanning for smartwatches (6s)...")

        def _scan_thread():
            async def _scan():
                return await scan_for_devices(timeout_sec=6.0)

            devices = asyncio.run(_scan())
            self.ui_queue.put(("scan_results", devices))

        threading.Thread(target=_scan_thread, daemon=True).start()

    def _start_queue_poller(self) -> None:
        """Polls the thread-safe queue to update UI elements on the main thread."""
        try:
            while True:
                msg_type, data = self.ui_queue.get_nowait()
                self._dispatch_ui_message(msg_type, data)
        except queue.Empty:
            pass
        self.root.after(25, self._start_queue_poller)

    def _dispatch_ui_message(self, msg_type: str, data: Any) -> None:
        if msg_type == "status":
            status, detail = data
            self._update_status(status, detail)
            if status == "CONNECTED_ARMED":
                self._is_connected = True
                self._is_connecting = False
                self.btn_connect.config(text="✕ Disconnect", state="normal", bg=ACCENT_RED)
                self.btn_scan.config(state="disabled")
                self.btn_buzz.config(state="normal", fg=TEXT_PRIMARY)
                self.btn_zero_accel.config(state="normal", fg=TEXT_PRIMARY)
            elif status in ("DISCONNECTED", "ERROR", "NOT_FOUND"):
                self._is_connected = False
                self._is_connecting = False
                self.btn_connect.config(text="⚡ Connect Watch", state="normal", bg=ACCENT_BLUE)
                self.btn_scan.config(state="normal")
                self.btn_buzz.config(state="disabled", fg=TEXT_MUTED)
                self.btn_zero_accel.config(state="disabled", fg=TEXT_MUTED)

        elif msg_type == "flick":
            count, time_left = data
            self.lbl_radar_state.config(text=f"Flick {count} registered! Window open ({time_left:.2f}s)")
            self._flash_tile(count)

        elif msg_type == "tick":
            count, remaining = data
            if count > 0:
                pct = (remaining / self.config.timing.gesture_window_sec) * 100.0
                self.progress_var.set(pct)
            else:
                self.progress_var.set(0.0)
                self.lbl_radar_state.config(text="Idle")

        elif msg_type == "action":
            action, now_str = data
            self.banner_action.config(
                text=f"{action.emoji} [{now_str}] DISPATCHED: {action.name.upper()} ({' + '.join(action.keys)})",
                fg=ACCENT_GREEN,
            )
            self._log(f"Executed: {action.name} ({' + '.join(action.keys)})")
            self._flash_tile(action.count, highlight_color=ACCENT_GREEN)

        elif msg_type == "scan_results":
            self.btn_scan.config(state="normal", text="🔍 Scan Nearby")
            devices = data
            matching = [d for d in devices if d.is_supported_watch]
            if matching:
                top = matching[0]
                self.mac_entry.delete(0, tk.END)
                self.mac_entry.insert(0, top.address)
                self._log(f"Auto-selected watch: {top.name} ({top.address}) RSSI: {top.rssi}dBm")
                self._update_status("DISCONNECTED", f"Found {top.name} ({top.address})")
            else:
                self._log(f"Scan complete: found {len(devices)} peripherals, but none matched known watch signatures.")
                self._update_status("DISCONNECTED", f"{len(devices)} devices found.")

    def _handle_buzz_watch(self) -> None:
        """Sends command to buzz/vibrate the watch to confirm connectivity."""
        if self._client and self._ble_loop and self._is_connected:
            asyncio.run_coroutine_threadsafe(self._client.buzz_watch(), self._ble_loop)
            self._log("Sent 'Find Watch' buzz signal to smartwatch.")

    def _handle_zero_accel(self) -> None:
        """Sends command to zero and calibrate the watch G-sensor."""
        if self._client and self._ble_loop and self._is_connected:
            asyncio.run_coroutine_threadsafe(self._client.calibrate_gsensor(), self._ble_loop)
            self._log("Sent G-Sensor calibration command (Opcode 0x52) to smartwatch.")

    def _flash_tile(self, count: int, highlight_color: str = ACCENT_BLUE) -> None:
        """Temporarily highlights the gesture action card."""
        clamped = min(count, 3)
        if clamped in self.tiles:
            tile_frame = self.tiles[clamped]["frame"]
            tile_frame.config(highlightbackground=highlight_color, highlightthickness=2)
            self.root.after(350, lambda: tile_frame.config(highlightbackground=BORDER, highlightthickness=1))


def launch_gui() -> None:
    """Launches the WatchGesture graphical desktop interface."""
    root = tk.Tk()
    app = WatchGestureApp(root)
    root.mainloop()


if __name__ == "__main__":
    launch_gui()

