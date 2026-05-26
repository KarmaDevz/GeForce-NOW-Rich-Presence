"""
Linux Window Title Detector for GeForce NOW Rich Presence.

Supports:
  - KDE Plasma (Wayland) via KWin scripting + journalctl
  - KDE Plasma (Wayland) via qdbus KWin scripting API  
  - X11 via xdotool (fallback)
  - GNOME Wayland via gdbus (experimental)

This module detects the active GeForce NOW window title on Linux.
GeForce NOW on Linux typically runs inside a browser (Chrome/Edge/Firefox)
or the official GFN Electron client.
"""

import subprocess
import logging
import os
import time
import tempfile
import re
from pathlib import Path
from typing import Optional, List, Tuple

logger = logging.getLogger('geforce_presence')

# Patterns to identify GFN windows and extract game name
# Formats observed:
#   "Game Name on GeForce NOW"            (EN - browser/client)
#   "Game Name - GeForce NOW"             (EN - client)
#   "GeForce NOW'da Game Name"            (TR - client: "GeForce NOW'da" = "on GeForce NOW")
#   "GeForce NOW'de Game Name"            (TR variant)
#   "GeForce NOW - Game Name"             (any)
#   "GeForce NOW" alone = lobby, no game
GFN_TITLE_PATTERNS = [
    # Dash prefix: "GeForce NOW - Game Name" or "GeForce NOW — Game Name"  ← check FIRST
    re.compile(r'^GeForce\s*NOW\s*[-–—]\s*(.+)', re.IGNORECASE),
    # Dash suffix: "Game Name - GeForce NOW"
    re.compile(r'^(.+?)\s*[-–—]\s*GeForce\s*NOW\s*$', re.IGNORECASE),
    # Turkish: "GeForce NOW'da/de/ta/te OyunAdı" — REQUIRES explicit apostrophe+suffix
    # Non-capturing group for suffix so game name is always group(1)
    re.compile(r"GeForce\s*NOW'(?:da|de|ta|te)\s+(.+)", re.IGNORECASE),
    # English: "Game Name on/in/via GeForce NOW"
    re.compile(r'(.+?)\s+(?:on|en|in|via)\s+GeForce\s*NOW\b', re.IGNORECASE),
]

# Lobby/idle titles — no game running
GFN_LOBBY_PATTERNS = [
    re.compile(r'^\s*GeForce\s*NOW\s*$', re.IGNORECASE),
    re.compile(r'^\s*GeForce\s*NOW\s*[|]\s*Home\s*$', re.IGNORECASE),
]

# GFN process/class names to look for
GFN_PROCESS_HINTS = [
    'geforcenow',
    'nvidia',
    'gfn',
]

# Browser class names (GFN might run inside these)
BROWSER_CLASSES = [
    'google-chrome', 'chromium', 'chromium-browser',
    'microsoft-edge', 'firefox', 'brave-browser',
    'vivaldi', 'opera',
]

# KWin script to enumerate all windows
_KWIN_SCRIPT_TEMPLATE = r"""
var clients = workspace.windowList();
for (var i = 0; i < clients.length; i++) {
    var c = clients[i];
    if (c.caption && c.caption.length > 0) {
        console.log("GFNRP:" + c.caption + "|||" + c.resourceClass + "|||" + c.resourceName);
    }
}
"""

_script_counter = 0


class LinuxWindowDetector:
    """Detects GeForce NOW game titles on Linux."""

    def __init__(self):
        self._session_type = os.environ.get('XDG_SESSION_TYPE', '').lower()
        self._desktop = os.environ.get('XDG_CURRENT_DESKTOP', '').lower()
        self._kwin_script_path = Path(tempfile.gettempdir()) / 'gfnrp_kwin_detect.js'
        self._last_windows: List[Tuple[str, str, str]] = []  # (caption, class, name)
        self._detection_method = None
        self._kwin_available = None
        self._xdotool_available = None
        
        # Rate limit for KWin script loading (align with monitoring interval ~10s)
        self._last_kwin_query = 0
        self._kwin_cooldown = 8.0  # seconds — refresh every monitoring cycle
        
        self._detect_capabilities()

    def _detect_capabilities(self):
        """Detect which window detection methods are available."""
        # Check for KDE KWin (Wayland-native)
        if 'kde' in self._desktop or 'plasma' in self._desktop:
            try:
                result = subprocess.run(
                    ['qdbus', 'org.kde.KWin', '/Scripting'],
                    capture_output=True, text=True, timeout=3
                )
                if result.returncode == 0 and 'loadScript' in result.stdout:
                    self._kwin_available = True
                    self._detection_method = 'kwin_scripting'
                    logger.info("🐧 Linux window detection: KDE KWin Scripting API will be used (Wayland-native)")
                    return
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass

        # Check for xdotool (X11/XWayland)
        try:
            result = subprocess.run(
                ['xdotool', '--version'],
                capture_output=True, text=True, timeout=3
            )
            if result.returncode == 0:
                self._xdotool_available = True
                self._detection_method = 'xdotool'
                logger.info("🐧 Linux window detection: xdotool will be used (X11/XWayland)")
                return
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        logger.warning("🐧 Linux window detection: No usable tools found! "
                        "Install KDE Plasma (qdbus) or xdotool.")
        self._detection_method = None

    def get_gfn_window_title(self) -> Optional[str]:
        """
        Get the current GeForce NOW game title.
        
        Returns:
            The game title if GFN is running and a game is active, None otherwise.
        """
        if self._detection_method == 'kwin_scripting':
            return self._detect_via_kwin()
        elif self._detection_method == 'xdotool':
            return self._detect_via_xdotool()
        return None

    def _detect_via_kwin(self) -> Optional[str]:
        """Detect GFN window title via KDE KWin scripting API."""
        now = time.time()
        if now - self._last_kwin_query < self._kwin_cooldown:
            # Use cached result
            return self._find_gfn_in_windows(self._last_windows)

        self._last_kwin_query = now

        # Use a temp file as IPC — write window list from KWin script, read in Python
        output_file = Path(tempfile.gettempdir()) / 'gfnrp_windows.txt'

        # KWin script: list all windows to a shared temp file via console.log + journalctl
        # But we use a marker-based approach with journalctl for reliability
        marker = f"GFNRP_{int(now * 1000)}"
        kwin_script = f"""
var clients = workspace.windowList();
console.log("{marker}_START");
for (var i = 0; i < clients.length; i++) {{
    var c = clients[i];
    if (c.caption && c.caption.length > 0) {{
        console.log("{marker}:" + c.caption + "|||" + c.resourceClass + "|||" + c.resourceName);
    }}
}}
console.log("{marker}_END");
"""
        try:
            self._kwin_script_path.write_text(kwin_script)

            global _script_counter
            script_name = f"gfnrp_{_script_counter}"
            _script_counter += 1

            # Load script
            load_result = subprocess.run(
                ['qdbus', 'org.kde.KWin', '/Scripting',
                 'org.kde.kwin.Scripting.loadScript',
                 str(self._kwin_script_path), script_name],
                capture_output=True, text=True, timeout=3
            )

            if load_result.returncode != 0:
                logger.debug(f"KWin script load error: {load_result.stderr.strip()}")
                return self._find_gfn_in_windows(self._last_windows)

            script_num = load_result.stdout.strip()

            # Record time just before running
            before_run = time.time()

            # Run script
            subprocess.run(
                ['qdbus', 'org.kde.KWin', f'/Scripting/Script{script_num}',
                 'org.kde.kwin.Script.run'],
                capture_output=True, text=True, timeout=3
            )

            # Wait for KWin to process + journal to receive
            time.sleep(0.4)

            # Stop script
            subprocess.run(
                ['qdbus', 'org.kde.KWin', f'/Scripting/Script{script_num}',
                 'org.kde.kwin.Script.stop'],
                capture_output=True, text=True, timeout=2
            )

            # Read from journalctl using our unique marker
            # Use '-6s' relative format (6 seconds ago) — broad enough to always catch it
            journal_result = subprocess.run(
                ['journalctl', '--user', '-S', '-6s',
                 '--no-pager', '-o', 'cat'],
                capture_output=True, text=True, timeout=5
            )

            windows = []
            if journal_result.returncode == 0:
                lines = journal_result.stdout.splitlines()
                in_block = False
                for line in lines:
                    if f'{marker}_START' in line:
                        in_block = True
                        continue
                    if f'{marker}_END' in line:
                        in_block = False
                        break
                    if in_block and f'{marker}:' in line:
                        data = line.split(f'{marker}:', 1)[1].strip()
                        parts = data.split('|||')
                        if len(parts) >= 3:
                            windows.append((parts[0], parts[1], parts[2]))

            if windows:
                self._last_windows = windows
                logger.debug(f"Retrieved {len(windows)} windows from KWin")

            return self._find_gfn_in_windows(self._last_windows)

        except subprocess.TimeoutExpired:
            logger.debug("KWin script timeout")
            return self._find_gfn_in_windows(self._last_windows)
        except Exception as e:
            logger.debug(f"KWin detection error: {e}")
            return self._find_gfn_in_windows(self._last_windows)


    def _detect_via_xdotool(self) -> Optional[str]:
        """Detect GFN window title via xdotool (X11/XWayland)."""
        try:
            # Search for windows with GeForce NOW in their title
            result = subprocess.run(
                ['xdotool', 'search', '--name', 'GeForce NOW'],
                capture_output=True, text=True, timeout=5
            )

            if result.returncode != 0 or not result.stdout.strip():
                # Also search for GFN electron client
                result = subprocess.run(
                    ['xdotool', 'search', '--name', 'GeForceNOW'],
                    capture_output=True, text=True, timeout=5
                )

            if result.returncode != 0 or not result.stdout.strip():
                return None

            window_ids = result.stdout.strip().split('\n')

            for wid in window_ids:
                wid = wid.strip()
                if not wid:
                    continue
                try:
                    name_result = subprocess.run(
                        ['xdotool', 'getwindowname', wid],
                        capture_output=True, text=True, timeout=2
                    )
                    if name_result.returncode == 0:
                        title = name_result.stdout.strip()
                        if title:
                            game = self._extract_game_from_title(title)
                            if game:
                                return title  # Return full title, extraction happens in find_active_game
                except Exception:
                    continue

            return None

        except Exception as e:
            logger.debug(f"xdotool detection error: {e}")
            return None

    def _find_gfn_in_windows(self, windows: List[Tuple[str, str, str]]) -> Optional[str]:
        """
        Find a GeForce NOW window and return the window title.
        Priority: GFN native client (class=GeForceNOW) > browser GFN tab.
        Returns the full raw window title (caller extracts game name).
        """
        if not windows:
            return None

        # Strategy 1: GFN native client — class is exactly 'GeForceNOW'
        for caption, wclass, wname in windows:
            if not caption:
                continue
            if wclass == 'GeForceNOW' or wname == 'GeForceNOW':
                return caption  # e.g. "GeForce NOW'da Counter-Strike 2" or "GeForce NOW"

        # Strategy 2: Any window with 'geforce now' in title (browser tab, etc.)
        for caption, wclass, wname in windows:
            if not caption:
                continue
            lower_caption = caption.lower()
            if 'geforce now' in lower_caption or 'geforcenow' in lower_caption:
                return caption

        # Strategy 3: Browser windows where GFN tab is active
        for caption, wclass, wname in windows:
            if not caption or not wclass:
                continue
            lower_class = wclass.lower()
            for browser in BROWSER_CLASSES:
                if browser in lower_class:
                    if 'geforce' in caption.lower():
                        return caption

        return None

    def extract_game_name(self, raw_title: str) -> Optional[str]:
        """
        Extract the game name from a raw GFN window title.
        Returns None if the title represents a lobby/idle screen (no game running).
        """
        if not raw_title:
            return None

        # Check if it's a lobby-only title (no game)
        for lobby_pat in GFN_LOBBY_PATTERNS:
            if lobby_pat.match(raw_title):
                return None

        # Try each extraction pattern
        for pattern in GFN_TITLE_PATTERNS:
            match = pattern.search(raw_title)
            if match:
                game = match.group(1).strip()
                # Sanity: ignore very short matches and known non-game strings
                if game and len(game) > 1 and game.lower() not in ('home', 'games', 'library'):
                    return game

        return None

    def is_gfn_running(self) -> bool:
        """Check if GeForce NOW is running (process-level check)."""
        import psutil
        try:
            for proc in psutil.process_iter(attrs=['name', 'cmdline']):
                name = (proc.info.get('name') or '').lower()
                cmdline = proc.info.get('cmdline') or []
                cmdline_str = ' '.join(cmdline).lower()

                # Check for GFN Electron client
                if 'geforcenow' in name:
                    return True

                # Check for GFN running in browser
                if any(browser in name for browser in ['chrome', 'chromium', 'firefox', 'edge', 'brave']):
                    if 'geforce' in cmdline_str or 'play.geforcenow.com' in cmdline_str:
                        return True
        except Exception:
            pass
        return False

    @property
    def method(self) -> Optional[str]:
        """Return the active detection method name."""
        return self._detection_method
