"""
Command Line Interface for WatchGesture.

Provides subcommands for device scanning, gesture control daemon execution,
raw packet sniffing, profile inspection, and GUI launching.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
from typing import Optional

from watchgesture.config import AppConfig
from watchgesture.core.client import WatchGestureClient
from watchgesture.core.dispatcher import ActionDispatcher
from watchgesture.core.engine import GestureEngine, GestureEvent
from watchgesture.core.protocol import CHAR_NOTIFY_FEE3, is_gesture_notification
from watchgesture.core.scanner import scan_for_devices
from watchgesture.profiles.default_profiles import BUILTIN_PROFILES, ActionItem


def setup_logging(verbose: bool = False) -> None:
    """Configures console logging with clean formatting."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def cmd_scan(args: argparse.Namespace) -> int:
    """Discovers nearby Bluetooth peripherals and identifies smartwatches."""
    print("=" * 70)
    print("   🔍 WATCHGESTURE - BLE DEVICE DISCOVERY SCANNER")
    print("=" * 70)
    print(f"Scanning for {args.timeout:.1f} seconds... Make sure watch screen is awake!\n")

    async def _scan():
        return await scan_for_devices(timeout_sec=args.timeout)

    devices = asyncio.run(_scan())

    if not devices:
        print("❌ No Bluetooth Low Energy devices detected. Check your Bluetooth radio.")
        return 1

    print(f"{'DEVICE NAME':<30} {'MAC ADDRESS':<20} {'RSSI':<10} {'STATUS'}")
    print("-" * 70)
    for dev in devices:
        status = "✅ SMARTWATCH" if dev.is_supported_watch else "   peripheral"
        print(f"{dev.name:<30} {dev.address:<20} {dev.rssi:<10} {status}")
    print("-" * 70)
    print("\nTip: Copy your watch MAC address and run:  python -m watchgesture run --mac <MAC>")
    return 0


def cmd_profiles(args: argparse.Namespace) -> int:
    """Lists built-in and configured gesture profiles."""
    print("=" * 70)
    print("   🎮 WATCHGESTURE - GESTURE PROFILES")
    print("=" * 70)
    config = AppConfig.load()

    for pid, profile in BUILTIN_PROFILES.items():
        is_active = " [ACTIVE]" if pid == config.active_profile else ""
        print(f"\n📦 Profile: {profile.name} (id: '{pid}'){is_active}")
        print(f"   {profile.description}")
        print("   Gestures:")
        for count in sorted(profile.actions.keys()):
            action = profile.actions[count]
            key_combo = " + ".join(action.keys)
            print(f"     • {count} Flick(s) ➡️  {action.emoji} {action.name:<18} [{key_combo}]")

    print("\n" + "=" * 70)
    return 0


def cmd_telemetry(args: argparse.Namespace) -> int:
    """Launches the real-time satellite GPS & biometric telemetry receiver."""
    from watchgesture.telemetry import TelemetryConfig, TelemetryPoint, TelemetryReceiver

    config = TelemetryConfig(
        upstream_topic=args.up_topic or "watchgesture_telemetry_up",
        downstream_topic=args.down_topic or "watchgesture_telemetry_down",
        server_port=args.port,
    )

    print("=" * 70)
    print("   🛰️  WATCHGESTURE - REAL-TIME GPS & BIOMETRIC TELEMETRY")
    print("=" * 70)
    print(f"Upstream Topic   : {config.upstream_topic} (Phone -> PC)")
    print(f"Downstream Topic : {config.downstream_topic} (PC -> Watch Screen)")
    print(f"HTTP Server Port : {config.server_port}")
    print("-" * 70)

    def on_point(p: TelemetryPoint) -> None:
        t_str = p.timestamp.strftime("%H:%M:%S")
        bpm_str = f"{p.bpm} BPM" if p.bpm else "--"
        steps_str = f"{p.steps}" if p.steps else "--"
        print(
            f"\r📍 [{t_str}] GPS: {p.lat:.5f}, {p.lon:.5f} (±{p.accuracy_m:.0f}m) | ❤️ Pulse: {bpm_str} | 👟 Steps: {steps_str}   ",
            end="",
            flush=True,
        )

    receiver = TelemetryReceiver(config=config, on_point_received=on_point)
    port = receiver.start_http_server(open_browser=not args.no_browser)
    receiver.start_listener()

    print(f"✅ Dashboard open at: http://localhost:{port}/live_map.html")
    print(f"📱 Phone Bridge: http://localhost:{port}/phone_bridge.html")
    print("\nType any message and press [ENTER] to push it to the watch screen (Ctrl+C to quit):\n")

    try:
        while True:
            txt = input().strip()
            if txt:
                success = receiver.send_message_to_watch(txt)
                status = "Delivered to cloud relay" if success else "Failed to send"
                print(f"💬 [{status}] -> '{txt}'")
    except (KeyboardInterrupt, EOFError):
        print("\n[Telemetry Server Stopped]")
    finally:
        receiver.stop()
    return 0


def cmd_telemetry_send(args: argparse.Namespace) -> int:
    """Sends a one-off text notification to the smartwatch screen via cloud relay."""
    from watchgesture.telemetry import TelemetryConfig, TelemetryReceiver

    down_topic = args.topic or "watchgesture_telemetry_down"
    config = TelemetryConfig(downstream_topic=down_topic)
    receiver = TelemetryReceiver(config=config)

    print(f"Sending message '{args.message}' to topic '{down_topic}'...")
    if receiver.send_message_to_watch(args.message):
        print("✅ Message successfully pushed to cloud relay!")
        return 0
    else:
        print("❌ Failed to push message.")
        return 1


def cmd_sniff(args: argparse.Namespace) -> int:
    """Sniffs raw notifications from the watch for reverse-engineering."""
    from bleak import BleakClient, BleakScanner
    from watchgesture.core.protocol import CHAR_WRITE_FEE2, make_keepalive_packet

    mac = args.mac or AppConfig.load().watch_mac
    print("=" * 70)
    print(f"   🕵️‍♂️ WATCHGESTURE RAW PACKET SNIFFER -> {mac}")
    print("=" * 70)

    async def _sniff():
        dev = await BleakScanner.find_device_by_address(mac, timeout=10.0)
        if not dev:
            print(f"❌ Could not find device with address {mac}.")
            return 1

        async with BleakClient(dev, timeout=15.0) as client:
            print("✅ Connected! Arming camera/gesture mode (0x66)...")
            await client.write_gatt_char(CHAR_WRITE_FEE2, make_keepalive_packet(), response=False)
            print("📡 Listening for incoming notifications across all pipes...\n")

            def handler(char, data: bytearray):
                now_str = time.strftime("%H:%M:%S")
                short_uuid = str(char.uuid)[:8].lower()
                hex_dump = bytes(data).hex(" ")
                is_flick = "⚡ [WRIST FLICK 0x66]" if is_gesture_notification(str(char.uuid), data) else ""
                print(f"[{now_str}] Pipe: {short_uuid} -> [{hex_dump}] {is_flick}")

            for s in client.services:
                for c in s.characteristics:
                    if "notify" in c.properties or "indicate" in c.properties:
                        try:
                            await client.start_notify(c.uuid, handler)
                        except Exception:
                            pass

            while client.is_connected:
                await asyncio.sleep(0.5)

    try:
        asyncio.run(_sniff())
    except KeyboardInterrupt:
        print("\n[Sniffer Stopped]")
    return 0


def cmd_gui(args: argparse.Namespace) -> int:
    """Launches the graphical user interface."""
    from watchgesture.gui.app import launch_gui
    launch_gui()
    return 0


def cmd_simulate(args: argparse.Namespace) -> int:
    """Simulates a gesture event locally to verify desktop key actions without BLE hardware."""
    config = AppConfig.load()
    profile_id = args.profile or config.active_profile
    profile = config.get_profile(profile_id)

    action = profile.get_action(args.flicks)
    if not action:
        print(f"❌ No action mapped for {args.flicks} flick(s) in profile '{profile.name}'.")
        return 1

    print("=" * 70)
    print("   🎮 WATCHGESTURE - LOCAL INPUT SIMULATION")
    print("=" * 70)
    print(f"Profile        : {profile.name} ('{profile_id}')")
    print(f"Simulating     : {args.flicks} Wrist Flick(s)")
    print(f"Target Action  : {action.emoji} {action.name} [{' + '.join(action.keys)}]")
    print(f"Description    : {action.description}")
    print("-" * 70)
    print("Executing keystroke in 1 second... (Switch to your target browser/media window!)")
    time.sleep(1.0)

    dispatcher = ActionDispatcher(profile=profile)
    event = GestureEvent(count=args.flicks, timestamp=time.time(), trigger_type="simulated")
    executed = dispatcher.dispatch(event)

    if executed:
        print(f"✅ DISPATCHED: {executed.name} ({' + '.join(executed.keys)})")
        return 0
    return 1


def cmd_snoop_extract(args: argparse.Namespace) -> int:
    """Extracts BTSnoop binary logs from an Android bug report text file."""
    from pathlib import Path
    from watchgesture.utils.snoop import decode_btsnooz, extract_btsnooz_from_text

    input_path = Path(args.bugreport)
    if not input_path.exists():
        print(f"❌ File not found: {args.bugreport}")
        return 1

    print(f"Reading {input_path.name}...")
    try:
        content = input_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as exc:
        print(f"❌ Failed to read file: {exc}")
        return 1

    btsnooz_data = extract_btsnooz_from_text(content)
    if not btsnooz_data:
        print("❌ No '--- BEGIN:BTSNOOP_LOG_SUMMARY' section found in the file.")
        return 1

    try:
        btsnoop_pcap = decode_btsnooz(btsnooz_data)
    except Exception as exc:
        print(f"❌ Failed to decode btsnooz data: {exc}")
        return 1

    out_path = Path(args.output or input_path.with_suffix(".pcap"))
    out_path.write_bytes(btsnoop_pcap)
    print(f"✅ Successfully extracted BTSnoop log ({len(btsnoop_pcap)} bytes) -> {out_path}")
    print("Tip: Open this file directly in Wireshark to inspect BLE ATT write/notify packets.")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    """Runs the main WatchGesture background controller daemon."""
    setup_logging(args.verbose)
    config = AppConfig.load()

    target_mac = args.mac or config.watch_mac
    profile_id = args.profile or config.active_profile
    profile = config.get_profile(profile_id)

    window_sec = args.window if args.window is not None else config.timing.gesture_window_sec
    min_gap_sec = args.gap if args.gap is not None else config.timing.min_gap_sec
    lockout_sec = args.lockout if args.lockout is not None else config.timing.lockout_duration_sec
    fast_rearm = args.fast_rearm if args.fast_rearm else config.fast_rearm

    print("=" * 70)
    print("   ⌚ WATCHGESTURE CONTROLLER DAEMON")
    print("=" * 70)
    print(f"Target Watch MAC : {target_mac}")
    print(f"Active Profile   : {profile.name} ('{profile_id}')")
    print(f"Timing Config    : Window={window_sec:.2f}s | MinGap={min_gap_sec:.2f}s | Lockout={lockout_sec:.2f}s")
    print(f"Fast Rearm (0x53): {'Enabled' if fast_rearm else 'Disabled'}")
    print("-" * 70)
    print("Mapped Controls:")
    for count in sorted(profile.actions.keys()):
        action = profile.actions[count]
        keys_str = " + ".join(action.keys)
        print(f"  • {count} Wrist Flick(s) ➡️  {action.emoji} {action.name:<18} [{keys_str}]")
    print("-" * 70)
    print("Connecting to smartwatch (ensure screen is awake)...\n")

    def on_dispatched(action: ActionItem, now_str: str) -> None:
        keys_str = " + ".join(action.keys)
        print(f"\n{action.emoji} [{now_str}] >>> DISPATCHED: {action.name.upper()} ({keys_str})")

    dispatcher = ActionDispatcher(profile=profile, on_action_dispatched=on_dispatched)

    def on_flick(count: int, time_left: float) -> None:
        if count == 1:
            print(f"\r⚡ [FLICK 1] Window open ({time_left:.1f}s)... snap again for 2x/3x", end="", flush=True)
        else:
            print(f" ➡️ [FLICK {count}!]", end="", flush=True)

    engine = GestureEngine(
        gesture_window_sec=window_sec,
        min_gap_sec=min_gap_sec,
        lockout_duration_sec=lockout_sec,
        on_flick=on_flick,
    )

    client = WatchGestureClient(
        target_mac=target_mac,
        engine=engine,
        dispatcher=dispatcher,
        fast_rearm=fast_rearm,
    )

    try:
        asyncio.run(client.connect_and_run(max_reconnect_attempts=3))
    except KeyboardInterrupt:
        print("\n\n[Stopped by User]")
        client.stop()
    return 0


def cmd_buzz(args: argparse.Namespace) -> int:
    """Sends a buzz/vibrate signal (Opcode 0x61) to the smartwatch."""
    from bleak import BleakClient, BleakScanner
    from watchgesture.core.protocol import CHAR_WRITE_FEE2, make_find_watch_packet

    mac = args.mac or AppConfig.load().watch_mac
    print(f"Connecting to watch ({mac}) to send buzz signal...")

    async def _buzz():
        dev = await BleakScanner.find_device_by_address(mac, timeout=8.0)
        if not dev:
            print(f"❌ Could not find device with address {mac}.")
            return 1
        async with BleakClient(dev, timeout=12.0) as client:
            await client.write_gatt_char(CHAR_WRITE_FEE2, make_find_watch_packet(), response=False)
            print("🔔 Buzz command sent! The watch should be vibrating.")
            return 0

    try:
        return asyncio.run(_buzz())
    except Exception as exc:
        print(f"❌ Error: {exc}")
        return 1


def build_parser() -> argparse.ArgumentParser:
    """Constructs the command-line argument parser with all subcommands."""
    parser = argparse.ArgumentParser(
        prog="watchgesture",
        description="Smartwatch BLE Wrist-Gesture Controller for Desktop Media & Navigation.",
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="Available subcommands")

    # Run command
    run_parser = subparsers.add_parser("run", help="Run the background gesture controller daemon")
    run_parser.add_argument("--mac", type=str, help="Bluetooth address of the smartwatch")
    run_parser.add_argument("--profile", type=str, choices=list(BUILTIN_PROFILES.keys()), help="Gesture action profile")
    run_parser.add_argument("--window", type=float, help="Gesture window in seconds (default: 1.00)")
    run_parser.add_argument("--gap", type=float, help="Debounce gap between flicks in seconds (default: 0.28)")
    run_parser.add_argument("--lockout", type=float, help="Post-action cooldown in seconds (default: 0.40)")
    run_parser.add_argument("--fast-rearm", action="store_true", help="Enable fast animation cancellation trick")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose debug logging")

    # Scan command
    scan_parser = subparsers.add_parser("scan", help="Scan for nearby BLE smartwatches")
    scan_parser.add_argument("--timeout", type=float, default=6.0, help="Scan timeout in seconds (default: 6.0)")

    # Sniff command
    sniff_parser = subparsers.add_parser("sniff", help="Sniff raw BLE packets from the watch")
    sniff_parser.add_argument("--mac", type=str, help="Target smartwatch MAC address")

    # Buzz command
    buzz_parser = subparsers.add_parser("buzz", help="Vibrate/buzz the smartwatch (Find Watch)")
    buzz_parser.add_argument("--mac", type=str, help="Target smartwatch MAC address")

    # Simulate command
    sim_parser = subparsers.add_parser("simulate", help="Locally simulate a gesture count without BLE hardware")
    sim_parser.add_argument("--flicks", type=int, choices=[1, 2, 3], default=1, help="Number of flicks to simulate")
    sim_parser.add_argument("--profile", type=str, choices=list(BUILTIN_PROFILES.keys()), help="Profile to test")

    # Snoop extract command
    snoop_parser = subparsers.add_parser("snoop-extract", help="Extract BTSnoop pcap from an Android bugreport text file")
    snoop_parser.add_argument("bugreport", type=str, help="Path to bugreport text file")
    snoop_parser.add_argument("-o", "--output", type=str, help="Destination .pcap file path")

    # Profiles command
    subparsers.add_parser("profiles", help="List available gesture profiles and hotkeys")

    # GUI command
    subparsers.add_parser("gui", help="Launch the graphical interface")

    # Telemetry commands
    telem_parser = subparsers.add_parser("telemetry", help="Launch live GPS & biometric telemetry receiver & HUD")
    telem_parser.add_argument("--up-topic", type=str, help="Upstream relay topic (Phone -> PC)")
    telem_parser.add_argument("--down-topic", type=str, help="Downstream relay topic (PC -> Watch)")
    telem_parser.add_argument("--port", type=int, default=8765, help="Local HTTP server port (default: 8765)")
    telem_parser.add_argument("--no-browser", action="store_true", help="Do not automatically launch browser")

    telem_send_parser = subparsers.add_parser("telemetry-send", help="Send a message to smartwatch screen via telemetry relay")
    telem_send_parser.add_argument("--message", "-m", type=str, required=True, help="Text message to push to watch screen")
    telem_send_parser.add_argument("--topic", type=str, help="Downstream relay topic (default: watchgesture_telemetry_down)")

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    """Entry point for CLI execution."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.subcommand:
        # Default to running the controller daemon if no subcommand given
        args = parser.parse_args(["run"] + (sys.argv[1:] if len(sys.argv) > 1 else []))

    if args.subcommand == "run":
        return cmd_run(args)
    elif args.subcommand == "scan":
        return cmd_scan(args)
    elif args.subcommand == "sniff":
        return cmd_sniff(args)
    elif args.subcommand == "buzz":
        return cmd_buzz(args)
    elif args.subcommand == "simulate":
        return cmd_simulate(args)
    elif args.subcommand == "snoop-extract":
        return cmd_snoop_extract(args)
    elif args.subcommand == "profiles":
        return cmd_profiles(args)
    elif args.subcommand == "gui":
        return cmd_gui(args)
    elif args.subcommand == "telemetry":
        return cmd_telemetry(args)
    elif args.subcommand == "telemetry-send":
        return cmd_telemetry_send(args)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())

