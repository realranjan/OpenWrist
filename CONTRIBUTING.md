# Contributing to WatchGesture

Thank you for your interest in contributing to **WatchGesture**! 

Whether you're adding support for a new smartwatch brand, creating new gesture profiles, fixing a bug, or improving documentation, this guide will help you get started quickly.

---

## 🛠️ Development Setup

1. **Fork and clone the repository:**
   ```powershell
   git clone https://github.com/<your-username>/watchgesture.git
   cd watchgesture
   ```

2. **Install the package in editable development mode:**
   ```powershell
   pip install -e .
   ```

3. **Verify the test suite passes:**
   ```powershell
   python -m unittest discover tests
   ```
   *All tests should pass in under 20 milliseconds.*

---

## 🎮 How to Add a New Gesture Profile

To add a new mapping profile (e.g. for Spotify, Discord, Figma, or a game):

1. Open [`src/watchgesture/profiles/default_profiles.py`](src/watchgesture/profiles/default_profiles.py).
2. Add your new profile definition to `BUILTIN_PROFILES`:

```python
BUILTIN_PROFILES["my_app"] = GestureProfile(
    id="my_app",
    name="My App Profile",
    description="Controls for My App media & navigation",
    actions={
        1: ActionItem(count=1, name="Primary Action", keys=["down"], emoji="👇", description="Next item"),
        2: ActionItem(count=2, name="Secondary Action", keys=["up"], emoji="👆", description="Previous item"),
        3: ActionItem(count=3, name="Boss Key", keys=["win", "d"], emoji="🛡️", description="Minimize app"),
    },
)
```

3. Add a test in [`tests/test_config.py`](tests/test_config.py) verifying your profile is registered.

---

## ⌚ How to Add Support for a New Smartwatch Brand

If you've reverse-engineered a new smartwatch (e.g. Noise, BoAt, Zeblaze, Amazfit, Colmi):

1. Read the [Reverse-Engineering Masterclass & Cookbook](docs/REVERSE_ENGINEERING.md#9-how-to-reverse-engineer-your-own-smartwatch-universal-cookbook) to extract the BTSnoop log and find the GATT UUIDs.
2. Add the vendor GATT service UUID and notify/write characteristic handles in [`src/watchgesture/core/protocol.py`](src/watchgesture/core/protocol.py).
3. If the watch uses different framing or opcodes, add helper builders (e.g. `make_<brand>_arm_packet()`) and an event matcher.
4. Add corresponding test cases in [`tests/test_protocol.py`](tests/test_protocol.py).

---

## 📜 Coding Guidelines & Standards

- **Strict Typing:** All function signatures and class definitions must have complete, strict type annotations. Avoid `Any` or `# type: ignore`.
- **Zero Placeholders:** Do not submit code with `TODO`, `pass`, `# placeholder`, or mock returns.
- **Zero External Bloat:** Use Python's standard library where possible (`http.server`, `urllib.request`, `json`, `dataclasses`).
- **Tests Required:** Any new feature, profile, or opcode builder must include unit tests that pass with `python -m unittest discover tests`.

---

## 🚀 Submitting a Pull Request

1. Create a feature branch:
   ```powershell
   git checkout -b feat/my-new-feature
   ```
2. Commit your changes with clear, conventional commit messages:
   ```powershell
   git commit -m "feat(profiles): add Discord push-to-talk gesture profile"
   ```
3. Push to your fork and submit a Pull Request against the `main` branch.
4. GitHub Actions CI will automatically test your PR on Windows, macOS, and Linux across Python 3.9 through 3.12.

