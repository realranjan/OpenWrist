"""
Main module execution entrypoint for WatchGesture.
Enables running via: python -m watchgesture
"""

import sys
from watchgesture.cli import main

if __name__ == "__main__":
    sys.exit(main())

