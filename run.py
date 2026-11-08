#!/usr/bin/env python
"""
WatchGesture - Quick Launcher Script.

Usage:
  python run.py             # Launches the graphical user interface (GUI)
  python run.py run         # Runs the background controller daemon
  python run.py scan        # Scans for nearby BLE smartwatches
  python run.py sniff       # Raw notification sniffer for debugging
  python run.py profiles    # Lists available gesture action profiles
"""

import sys
from pathlib import Path

# Ensure src/ is in python path
src_dir = Path(__file__).resolve().parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from watchgesture.cli import main

if __name__ == "__main__":
    if len(sys.argv) == 1:
        # Default with no arguments: open the GUI
        sys.exit(main(["gui"]))
    else:
        sys.exit(main())

