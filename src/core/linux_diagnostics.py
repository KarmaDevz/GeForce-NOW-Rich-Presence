import glob
import os
import socket
from pathlib import Path

import psutil

from src.core.linux_gfn_log import find_native_log_path, game_from_native_log as _game_from_native_log
from src.core.linux_window_detector import LinuxWindowDetector
from src.core.utils import CONFIG_DIR, safe_json_load


def _runtime_dir() -> Path:
    return Path(os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}")


def _socket_connects(path: str) -> bool:
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(1)
            client.connect(path)
        return True
    except Exception:
        return False


def discord_ipc_paths() -> list[tuple[str, bool]]:
    base = _runtime_dir()
    candidates = []
    for subdir in (".", "snap.discord", "app/com.discordapp.Discord", "app/com.discordapp.DiscordCanary"):
        candidates.extend(glob.glob(str(base / subdir / "discord-ipc-*")))
    seen = set()
    result = []
    for path in candidates:
        if path in seen:
            continue
        seen.add(path)
        result.append((path, _socket_connects(path)))
    return result


def discord_package_type() -> str:
    found_discord = False
    try:
        for proc in psutil.process_iter(attrs=["name", "exe", "cmdline"]):
            name = (proc.info.get("name") or "").lower()
            exe = proc.info.get("exe") or ""
            cmdline = " ".join(proc.info.get("cmdline") or [])
            combined = f"{exe} {cmdline}".lower()
            if "discord" not in name and "discord" not in combined:
                continue
            found_discord = True
            if "/snap/discord/" in combined:
                return "snap"
            if "flatpak" in combined or "/app/" in combined or "com.discordapp.discord" in combined:
                return "flatpak"
            if "/usr/share/discord" in combined or "/opt/discord" in combined or "/usr/bin/discord" in combined or "/.config/discord/" in combined:
                return "deb/apt"
    except Exception:
        pass
    return "unknown-running" if found_discord else "not-running"


def gfn_processes() -> list[str]:
    matches = []
    try:
        for proc in psutil.process_iter(attrs=["name", "cmdline"]):
            name = proc.info.get("name") or ""
            cmdline = " ".join(proc.info.get("cmdline") or [])
            combined = f"{name} {cmdline}".lower()
            if "geforcenow" in combined or "geforce now" in combined or "play.geforcenow.com" in combined:
                matches.append(f"{proc.pid}: {name} {cmdline}".strip())
    except Exception:
        pass
    return matches[:8]


def gfn_native_log_path():
    return find_native_log_path()


def game_from_native_log():
    games = safe_json_load(CONFIG_DIR / "games_config_merged.json") or {}
    game, path = _game_from_native_log(games)
    return game, str(path) if path else None


def build_diagnostics() -> str:
    lines = ["GeForce NOW Rich Presence Linux diagnostics"]
    lines.append(f"Session type: {os.environ.get('XDG_SESSION_TYPE', 'unknown')}")
    lines.append(f"Desktop: {os.environ.get('XDG_CURRENT_DESKTOP', 'unknown')}")
    lines.append(f"Runtime dir: {_runtime_dir()}")

    package = discord_package_type()
    lines.append(f"Discord package: {package}")
    ipc_paths = discord_ipc_paths()
    if ipc_paths:
        for path, ok in ipc_paths:
            lines.append(f"Discord IPC: {path} ({'connects' if ok else 'not connectable'})")
    else:
        lines.append("Discord IPC: not found")
    if package == "snap":
        lines.append("Warning: Snap Discord often does not expose Rich Presence IPC to normal apps.")

    detector = LinuxWindowDetector()
    raw_title = detector.get_gfn_window_title()
    game_from_title = detector.extract_game_name(raw_title) if raw_title else None
    lines.append(f"Window detector: {detector.method or 'none'}")
    lines.append(f"GFN window title: {raw_title or 'not found'}")
    lines.append(f"Game from title: {game_from_title or 'not found'}")

    processes = gfn_processes()
    lines.append(f"GFN processes: {len(processes)} found")
    for process in processes:
        lines.append(f"  {process}")

    log_game, log_path = game_from_native_log()
    lines.append(f"Native GFN log: {log_path or 'not found'}")
    lines.append(f"Game from native log: {log_game or 'not found'}")

    final_game = game_from_title or log_game
    source = "window title" if game_from_title else ("native log" if log_game else "none")
    lines.append(f"Final detected game: {final_game or 'not found'}")
    lines.append(f"Detection source: {source}")
    return "\n".join(lines)
