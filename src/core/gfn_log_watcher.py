import os
import re
import logging
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger('geforce_presence')

# GFN truncates log entries by byte length, so entries with multi-byte characters
# lose their trailing "]" and newline and get glued to the next entry. Because of that
# we search for events anywhere in the text instead of matching whole lines.
EVENT_RE = re.compile(
    r'ApplicationClass\s+Launch game (?P<title>.+?) \[[0-9a-fA-F-]'
    r'|StreamerManagerService\s+Advancing to state: (?P<state>\w+)'
)

END_STATES = {"PostSessionConnection", "PostStreaming", "Done"}


def default_log_paths() -> List[Path]:
    home = Path.home()
    state_home = Path(os.environ.get("XDG_STATE_HOME") or home / ".local" / "state")
    return [
        # Official Flatpak (com.nvidia.geforcenow)
        home / ".var" / "app" / "com.nvidia.geforcenow" / ".local" / "state" / "NVIDIA" / "GeForceNOW" / "console.log",
        # Non-Flatpak install
        state_home / "NVIDIA" / "GeForceNOW" / "console.log",
    ]


class GfnLogWatcher:
    """Tails GeForce NOW's console.log to know which game is currently streaming."""

    def __init__(self, paths: Optional[List[Path]] = None):
        self.paths = paths if paths is not None else default_log_paths()
        self.reset()

    def reset(self):
        self._path = None
        self._inode = None
        self._offset = 0
        self._pending = b""
        self.title = None
        self.state = None
        self.streamed = False

    def _find_log(self) -> Optional[Path]:
        for path in self.paths:
            if path.is_file():
                return path
        return None

    def poll(self):
        path = self._find_log()
        if path is None:
            if self._path is not None:
                self.reset()
            return

        try:
            st = path.stat()
            # GFN rotates console.log -> console.log.bak on every start
            if path != self._path or st.st_ino != self._inode or st.st_size < self._offset:
                self.reset()
                self._path = path
                self._inode = st.st_ino

            if st.st_size == self._offset:
                return

            with open(path, "rb") as f:
                f.seek(self._offset)
                data = f.read()
            self._offset += len(data)
        except OSError as e:
            logger.debug(f"Error leyendo log de GeForce NOW ({path}): {e}")
            return

        data = self._pending + data
        # Keep an incomplete last line for the next poll
        cut = data.rfind(b"\n") + 1
        self._pending = data[cut:]
        self._parse(data[:cut].decode("utf-8", errors="ignore"))

    def _parse(self, text: str):
        for m in EVENT_RE.finditer(text):
            if m.group("title"):
                self.title = m.group("title").strip()
                self.state = None
                self.streamed = False
            else:
                self.state = m.group("state")
                if self.state == "Streaming":
                    self.streamed = True

    def active_title(self) -> Optional[str]:
        self.poll()
        if self.title and self.streamed and self.state not in END_STATES:
            return self.title
        return None
