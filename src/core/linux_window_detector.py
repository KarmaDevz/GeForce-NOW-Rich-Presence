"""Linux GeForce NOW window title detection."""

import logging
import re
import shutil
import subprocess
from typing import Optional

logger = logging.getLogger("geforce_presence")

GFN_TITLE_PATTERNS = [
    re.compile(r"^GeForce\s*NOW\s*[-–—]\s*(.+)", re.IGNORECASE),
    re.compile(r"^(.+?)\s*[-–—]\s*GeForce\s*NOW\s*$", re.IGNORECASE),
    re.compile(r"GeForce\s*NOW'(?:da|de|ta|te)\s+(.+)", re.IGNORECASE),
    re.compile(r"(.+?)\s+(?:on|en|in|via)\s+GeForce\s*NOW\b", re.IGNORECASE),
]

GFN_LOBBY_PATTERNS = [
    re.compile(r"^\s*GeForce\s*NOW\s*$", re.IGNORECASE),
    re.compile(r"^\s*GeForce\s*NOW\s*[|]\s*Home\s*$", re.IGNORECASE),
]

BROWSER_PROCESS_NAMES = ("chrome", "chromium", "firefox", "edge", "brave", "vivaldi", "opera")


class LinuxWindowDetector:
    """Detect GeForce NOW game titles on Linux using xdotool when available."""

    def __init__(self):
        self._method = "xdotool" if shutil.which("xdotool") else None
        if self._method:
            logger.info("🐧 Linux window detection: xdotool will be used (X11/XWayland)")
        else:
            logger.warning("🐧 Linux window detection: xdotool not found. Native GFN logs will be used when available.")

    @property
    def method(self) -> Optional[str]:
        return self._method

    def get_gfn_window_title(self) -> Optional[str]:
        if self._method != "xdotool":
            return None

        for query in ("GeForce NOW", "GeForceNOW", "play.geforcenow.com"):
            title = self._title_from_xdotool_query(query)
            if title:
                return title
        return None

    def _title_from_xdotool_query(self, query: str) -> Optional[str]:
        try:
            result = subprocess.run(
                ["xdotool", "search", "--name", query],
                capture_output=True,
                text=True,
                timeout=5,
            )
        except Exception as e:
            logger.debug(f"xdotool search failed for {query!r}: {e}")
            return None

        if result.returncode != 0 or not result.stdout.strip():
            return None

        for window_id in result.stdout.splitlines():
            window_id = window_id.strip()
            if not window_id:
                continue
            title = self._window_title(window_id)
            if title and (self.extract_game_name(title) or self._is_gfn_lobby(title)):
                return title
        return None

    def _window_title(self, window_id: str) -> Optional[str]:
        try:
            result = subprocess.run(
                ["xdotool", "getwindowname", window_id],
                capture_output=True,
                text=True,
                timeout=2,
            )
        except Exception:
            return None
        if result.returncode != 0:
            return None
        return result.stdout.strip() or None

    def extract_game_name(self, raw_title: str) -> Optional[str]:
        if not raw_title or self._is_gfn_lobby(raw_title):
            return None

        for pattern in GFN_TITLE_PATTERNS:
            match = pattern.search(raw_title)
            if not match:
                continue
            game = match.group(1).strip()
            if game and len(game) > 1 and game.lower() not in ("home", "games", "library"):
                return game
        return None

    def _is_gfn_lobby(self, raw_title: str) -> bool:
        return any(pattern.match(raw_title) for pattern in GFN_LOBBY_PATTERNS)

    def is_gfn_running(self) -> bool:
        try:
            import psutil

            for proc in psutil.process_iter(attrs=["name", "cmdline"]):
                name = (proc.info.get("name") or "").lower()
                cmdline = " ".join(proc.info.get("cmdline") or []).lower()
                if "geforcenow" in name or "geforce now" in cmdline or "play.geforcenow.com" in cmdline:
                    return True
                if any(browser in name for browser in BROWSER_PROCESS_NAMES) and "geforce" in cmdline:
                    return True
        except Exception:
            pass
        return False
