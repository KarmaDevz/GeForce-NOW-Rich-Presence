import os
import re
from pathlib import Path
from typing import Optional

DEFAULT_NATIVE_LOG_PATHS = (
    Path(".var/app/com.nvidia.geforcenow/.local/state/NVIDIA/GeForceNOW/CxNative_GeForceNOW.log"),
    Path(".local/state/NVIDIA/GeForceNOW/CxNative_GeForceNOW.log"),
    Path(".config/NVIDIA/GeForceNOW/CxNative_GeForceNOW.log"),
)

_STREAM_START_RE = re.compile(
    r"^(?P<ts>\S+)\s+.*?onStreamStart.*?"
    r"drsProfileName:(?P<name>.*?)\s+"
    r"shortName:(?P<short>\S*)\s+"
    r"cmsId:(?P<cms>\d+)",
    re.MULTILINE,
)
_STREAM_STOP_RE = re.compile(
    r"^(?P<ts>\S+)\s+.*?onStreamStop\s+processId:(?P<cms>\d+)",
    re.MULTILINE,
)


def find_native_log_path(env_path: Optional[str] = None, home: Optional[Path] = None) -> Optional[Path]:
    candidates = []
    env_path = env_path if env_path is not None else os.getenv("GFN_LOG_PATH", "").strip()
    if env_path:
        candidates.append(Path(env_path).expanduser())

    base_home = Path.home() if home is None else Path(home)
    candidates.extend(base_home / relative for relative in DEFAULT_NATIVE_LOG_PATHS)

    return next((path for path in candidates if path.exists()), None)


def parse_native_log_text(text: str) -> tuple[Optional[str], Optional[str]]:
    events = []
    for match in _STREAM_START_RE.finditer(text):
        events.append((match.start(), "start", match.group("cms"), match.group("name").strip()))
    for match in _STREAM_STOP_RE.finditer(text):
        events.append((match.start(), "stop", match.group("cms"), None))

    active = {}
    for _, kind, cms_id, name in sorted(events, key=lambda item: item[0]):
        if kind == "start":
            active[cms_id] = name
        else:
            active.pop(cms_id, None)

    if not active:
        return None, None
    cms_id, name = next(reversed(active.items()))
    return cms_id, name or None


def game_name_for_cms_id(cms_id: str, games_map: Optional[dict]) -> Optional[str]:
    if not cms_id or not games_map:
        return None
    cms_id = str(cms_id)
    for key, info in games_map.items():
        if str((info or {}).get("cmsId") or "") == cms_id:
            return (info or {}).get("name") or key
    return None


def game_from_native_log(games_map: Optional[dict] = None, log_path: Optional[Path] = None) -> tuple[Optional[str], Optional[Path]]:
    path = Path(log_path) if log_path else find_native_log_path()
    if not path:
        return None, None

    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None, path

    cms_id, raw_name = parse_native_log_text(text)
    if not cms_id:
        return None, path
    return game_name_for_cms_id(cms_id, games_map) or raw_name, path
