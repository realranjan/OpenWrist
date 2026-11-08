"""
Default gesture mapping profiles for WatchGesture.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ActionItem:
    """Represents an actionable command triggered by a gesture count."""
    count: int
    name: str
    description: str
    emoji: str
    action_type: str  # "key", "hotkey", "vk", or "custom"
    keys: List[str]   # e.g. ["down"], ["win", "d"], ["space"]
    vk_codes: Optional[List[int]] = None


@dataclass
class GestureProfile:
    """A collection of gesture actions tuned for a specific app or activity."""
    id: str
    name: str
    description: str
    actions: Dict[int, ActionItem] = field(default_factory=dict)

    def get_action(self, count: int) -> Optional[ActionItem]:
        """Returns the corresponding action item, clamping high counts to maximum mapped."""
        if not self.actions:
            return None
        max_count = max(self.actions.keys())
        clamped = min(count, max_count)
        return self.actions.get(clamped)


BUILTIN_PROFILES: Dict[str, GestureProfile] = {
    "reels": GestureProfile(
        id="reels",
        name="Instagram Reels",
        description="Flick down for next reel, double-flick up for previous, triple-flick for Boss Key.",
        actions={
            1: ActionItem(1, "Next Reel", "Scroll down", "👇", "key", ["down"]),
            2: ActionItem(2, "Previous Reel", "Scroll up", "👆", "key", ["up"]),
            3: ActionItem(3, "Boss Key", "Minimize & show desktop", "🛡️", "hotkey", ["win", "d"]),
        },
    ),
    "youtube_shorts": GestureProfile(
        id="youtube_shorts",
        name="YouTube Shorts / TikTok",
        description="Navigate vertical shorts and mute video instantly.",
        actions={
            1: ActionItem(1, "Next Short", "Scroll down", "👇", "key", ["down"]),
            2: ActionItem(2, "Previous Short", "Scroll up", "👆", "key", ["up"]),
            3: ActionItem(3, "Toggle Mute", "Mute / Unmute playback", "🔇", "key", ["m"]),
        },
    ),
    "media": GestureProfile(
        id="media",
        name="Media Player & Spotify",
        description="Play/pause track, skip forward, or toggle system mute.",
        actions={
            1: ActionItem(1, "Play / Pause", "Toggle media playback", "⏯️", "key", ["playpause"]),
            2: ActionItem(2, "Next Track", "Skip to next track", "⏭️", "key", ["nexttrack"]),
            3: ActionItem(3, "Mute Volume", "Toggle system audio mute", "🔇", "key", ["volumemute"]),
        },
    ),
    "presentation": GestureProfile(
        id="presentation",
        name="Slides & Presentation",
        description="Advance slides during PowerPoint or Keynote presentations.",
        actions={
            1: ActionItem(1, "Next Slide", "Advance to next slide", "👉", "key", ["right"]),
            2: ActionItem(2, "Previous Slide", "Return to previous slide", "👈", "key", ["left"]),
            3: ActionItem(3, "Blackout Screen", "Toggle presenter screen blanking", "⬛", "key", ["b"]),
        },
    ),
    "reading": GestureProfile(
        id="reading",
        name="Document / Page Reader",
        description="Page down / Page up through long articles, PDFs, or manga.",
        actions={
            1: ActionItem(1, "Page Down", "Scroll one page down", "📄", "key", ["pagedown"]),
            2: ActionItem(2, "Page Up", "Scroll one page up", "📃", "key", ["pageup"]),
            3: ActionItem(3, "Go to Top", "Jump to top of document", "🔝", "key", ["home"]),
        },
    ),
}

