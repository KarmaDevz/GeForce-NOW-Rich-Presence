import time
import logging
import psutil
import subprocess
import tempfile
import shutil
try:
    from rapidfuzz import fuzz, process
except ImportError:
    import difflib
    fuzz = None
import re
import sys
from pathlib import Path
import os
import json
from typing import Optional, Dict, List
import threading
from src.core.app_launcher import AppLauncher

from PyQt5.QtCore import QObject, pyqtSignal, QTimer

from pypresence import Presence
from src.core.utils import safe_json_load, save_json, CONFIG_DIR, BASE_DIR, DISCORD_CACHE_PATH, DISCORD_DETECTABLE_URL, DISCORD_CACHE_TTL, DISCORD_AUTO_APPLY_THRESHOLD, DISCORD_ASK_TIMEOUT, IS_WINDOWS, IS_MACOS, IS_LINUX
from src.core.steam_scraper import SteamScraper, find_steam_appid_by_name
from src.core.cookie_manager import CookieManager
from src.core.game_presets import get_preset

# Linux window detection
if IS_LINUX:
    try:
        from src.core.linux_window_detector import LinuxWindowDetector
    except ImportError:
        LinuxWindowDetector = None

# Import win32 libs inside methods or here if safe
if IS_WINDOWS:
    try:
        import win32gui
        import win32process
    except ImportError:
        win32gui = None
        win32process = None
else:
    win32gui = None
    win32process = None

logger = logging.getLogger('geforce_presence')

class PresenceManager(QObject):
    # Signals to communicate with UI
    log_message = pyqtSignal(str, str) # level, message
    log_message = pyqtSignal(str, str) # level, message
    request_match_selection = pyqtSignal(str, list) # game_key, candidates
    sync_progress = pyqtSignal(int, int, int, str) # current, total, updated, eta_str
    download_progress = pyqtSignal(int, int) # current_bytes, total_bytes
    sync_finished = pyqtSignal(int, int) # updated_count, total_processed
    sync_error = pyqtSignal(str)
    gfn_error_detected = pyqtSignal()
    
    def __init__(self, client_id: str, games_map: dict, cookie_manager: CookieManager, test_rich_url: str, texts: Dict,
                 update_interval: int = 10, keep_alive: bool = False):
        super().__init__()
        # in __init__
        self._match_cache_lock = threading.Lock()
        self._apps_lock = threading.Lock()

        # to avoid duplicate work
        self._ongoing_match_jobs = set()          # games with match in progress
        self._last_match_attempt = {}             # {game_key: timestamp}
        self._match_attempt_counts = {}           # {game_key: count}
        self.MATCH_ATTEMPT_COOLDOWN = 60         # seconds between attempts for the same game

        self._http_session = None
        self.client_id = client_id
        self.games_map = games_map
        self.cookie_manager = cookie_manager
        self.test_rich_url = test_rich_url
        self.texts = texts
        self.update_interval = update_interval
        self.keep_alive = keep_alive
        
        self.fake_proc = None
        self.fake_exec_path = None
        self.last_log_message = None
        self.rpc = None
        self._connected_client_id = None
        
        self.active_quests = {} # {game_id: {proc: Popen, start_time: ts, name: str, finished: bool}}
        
        self.scraper = SteamScraper(self.cookie_manager.env_cookie, test_rich_url)

        self.last_game = None
        self.forced_game = None
        self._last_forced_game = None

        self._force_stop_time = 0
        self.current_game_start_time = None
        
        # Linux window detector
        self._linux_detector = None
        if IS_LINUX and LinuxWindowDetector is not None:
            try:
                self._linux_detector = LinuxWindowDetector()
            except Exception as e:
                logger.warning(f"Linux window detector could not be started: {e}")

        self.cleanup_all_fake_processes() # Clean startup

        self._connect_rpc()
        
        # Timer for the main loop
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_presence)
        
        # Cache for match results
        self._match_cache = {}
        # Cache for normalized apps list
        self._cached_apps_normalized = None
        self._last_apps_ts = 0

    def cleanup_all_fake_processes(self):
        """
        Kill any process running from the temp directories:
        - discord_fake_game
        - discord_quests
        """
        logger.info("🧹 Cleaning residual fake processes...")
        temp_dirs = [
            str(Path(tempfile.gettempdir()) / "discord_fake_game").lower(),
            str(Path(tempfile.gettempdir()) / "discord_quests").lower()
        ]
        
        count = 0
        try:
            for proc in psutil.process_iter(['pid', 'name', 'exe', 'cmdline']):
                try:
                    p_exe = (proc.info.get('exe') or "").lower()
                    p_cmd = (proc.info.get('cmdline') or [])
                    p_cmd_str = " ".join(p_cmd).lower()
                    
                    matched = False
                    for td in temp_dirs:
                        if td in p_exe or any(td in arg.lower() for arg in p_cmd):
                            matched = True
                            break
                    
                    if matched:
                        logger.info(f"🔪 Killing residual process: {proc.info['name']} (PID {proc.pid})")
                        proc.terminate()
                        try:
                            proc.wait(timeout=2)
                        except psutil.TimeoutExpired:
                            proc.kill()
                        count += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                     continue
        except Exception as e:
            logger.error(f"Error in initial cleanup: {e}")
        
        if count > 0:
            logger.info(f"✅ Cleaned up {count} residual processes.")
        else:
            logger.info("✅ No residual processes found.")

    def update_cookie(self, new_cookie: str):
        if new_cookie:
            self.cookie_manager.env_cookie = new_cookie
            self.scraper.set_cookie(new_cookie)
            logger.info("🍪 Cookie updated in PresenceManager and Scraper.")
        
    def start_monitoring(self):
        logger.info("🟢 Starting presence monitor...")
        self.timer.start(self.update_interval * 1000)

        # Only start sync if there are games with missing data and after 5s to let the app start
        # REMOVED: Automatic sync on startup to save resources
        # def maybe_start_sync():
        #     time.sleep(5)
        #     if self._should_sync():
        #         threading.Thread(target=self.sync_missing_game_details, daemon=True).start()
        # threading.Thread(target=maybe_start_sync, daemon=True).start()

    def _should_sync(self):
        for info in self.games_map.values():
            if not info.get("client_id") or not info.get("executable_path"):
                return True
        return False

    def check_discord_cache_status(self):
        if not DISCORD_CACHE_PATH.exists():
            return {"status": "MISSING", "hours": 0}
        
        try:
            data = safe_json_load(DISCORD_CACHE_PATH)
            ts = data.get("_ts", 0)
            diff = time.time() - ts
            hours = diff / 3600
            if diff < DISCORD_CACHE_TTL:
                return {"status": "FRESH", "hours": hours}
            else:
                return {"status": "STALE", "hours": hours}
        except:
            return {"status": "ERROR", "hours": 0}

    def cancel_sync(self):
        self._cancel_sync_flag = True

    def sync_missing_game_details(self, force_download: bool = False):
        """
        Iterates over all games in the configuration and, if data (client_id, executable_path) is missing,
        tries to find them in the Discord cache.
        """
        logger.info(f"🔄 Starting mass sync of games with Discord (Force={force_download})...")
        self._cancel_sync_flag = False
        try:
            apps = self._fetch_discord_apps_cached(force_download=force_download)
            if not apps:
                logger.warning("⚠️ No Discord cache available for sync.")
                # Force download if cache is empty/missing
                apps = self._fetch_discord_apps_cached(force_download=True)
                if not apps:
                     self.sync_error.emit("Could not fetch Discord applications list.")
                     return

            updated_count = 0
            games_to_update = {}
            
            # Create a copy to iterate safely
            current_games = dict(self.games_map)
            total_games = len(current_games)
            processed = 0
            
            # Identify games that actually need syncing
            games_to_process = []
            for game_key, info in current_games.items():
                if not info.get("client_id") or not info.get("executable_path"):
                    games_to_process.append((game_key, info))
                else:
                    processed += 1 # Already done
            
            # Update progress with skipping count instantly
            if processed > 0:
                 self.sync_progress.emit(processed, total_games, updated_count, "Calculating...")
                 
            from concurrent.futures import ThreadPoolExecutor
            import threading
            
            progress_lock = threading.Lock()
            
            start_time = time.time()
            last_emit_time = 0
            
            def format_eta(seconds):
                if seconds < 0: return "..."
                if seconds > 3600:
                    return f"{int(seconds // 3600)}h {int((seconds % 3600) // 60)}m"
                m, s = divmod(int(seconds), 60)
                return f"{m:02d}:{s:02d}"
            
            def process_game(item):
                game_key, info = item
                if self._cancel_sync_flag:
                    return None
                    
                changed_info = None
                candidates = self._find_discord_matches(game_key, max_candidates=1)
                
                if candidates:
                    top = candidates[0]
                    if top.get("score", 0) >= DISCORD_AUTO_APPLY_THRESHOLD:
                        # We found a match!
                        match = top
                        entry = info.copy()
                        changed = False
                        
                        if match.get("exe") and not entry.get("executable_path"):
                            entry["executable_path"] = match["exe"]
                            changed = True
                        
                        if match.get("id") and not entry.get("client_id"):
                            entry["client_id"] = match["id"]
                            changed = True
                        
                        if changed:
                            changed_info = (game_key, entry)
                
                return changed_info

            # Process in parallel
            with ThreadPoolExecutor(max_workers=min(32, (os.cpu_count() or 1) * 4)) as executor:
                for result in executor.map(process_game, games_to_process):
                    if self._cancel_sync_flag:
                        logger.info("🛑 Sync cancelled by the user.")
                        break
                        
                    with progress_lock:
                        processed += 1
                        if result:
                            key, val = result
                            games_to_update[key] = val
                            updated_count += 1
                            if updated_count % 10 == 0:
                                logger.debug(f"Sync progress: {updated_count} games updated...")
                        
                        current_time = time.time()
                        
                        # Throttle to approximately 10 frames per second max, OR last emit, to prevent GUI freezing.
                        if (current_time - last_emit_time) >= 0.1 or processed == total_games:
                            # Calculate ETA 
                            elapsed = current_time - start_time
                            # To prevent division by zero or unrealistic ETA on first items
                            if elapsed > 1 and processed > 0:
                                items_per_sec = processed / elapsed
                                remaining = total_games - processed
                                eta = remaining / items_per_sec if items_per_sec > 0 else -1
                                eta_str = format_eta(eta)
                            else:
                                eta_str = "Calculating..."
                            
                            self.sync_progress.emit(processed, total_games, updated_count, eta_str)
                            last_emit_time = current_time

            if updated_count > 0:
                # Bulk update
                config_path = CONFIG_DIR / "games_config_merged.json"
                # Reload to be safe before saving
                games_config = safe_json_load(config_path) or {}
                
                for k, v in games_to_update.items():
                    # Merge updates
                    if k in games_config:
                        games_config[k].update(v)
                    else:
                        games_config[k] = v
                    # Also update memory map
                    if k in self.games_map:
                        self.games_map[k].update(v)

                save_json(games_config, config_path)
                logger.info(f"✅ Sync completed: {updated_count} games updated with Discord data.")
            else:
                logger.info("✅ Sync completed: No updates required.")
            
            self.sync_finished.emit(updated_count, total_games)

        except Exception as e:
            logger.error(f"❌ Error in mass sync: {e}")
            self.sync_error.emit(str(e))

    def stop_monitoring(self):
        self.timer.stop()
        self.close()

    def _connect_rpc(self, client_id: Optional[str] = None):
        if client_id !="1095416975028650046":
            try:
                if self.rpc:
                    try:
                        self.rpc.close()
                    except Exception:
                        pass
                client_id = client_id or self.client_id
                self.rpc = Presence(client_id)
                self.rpc.connect()
                self._connected_client_id = client_id
                logger.info(f"✅ Connected to Discord RPC with client_id={client_id}")
            except Exception as e:
                if e == "Could not find Discord installed and running on this machine.":
                    logger.error(f"💨 Relaunching Discord...")
                    AppLauncher.launch_discord()
                else:
                    logger.error(f"❌ Error connecting to Discord RPC: {e}")
                self.rpc = None
                self._connected_client_id = None

    def stop_force_game(self):
        """Stops forcing a game and returns to automatic detection"""
        if self.forced_game:
            forced_game_name = self.forced_game.get('name', 'Unknown')
            logger.info(f"🧹 Stopping forcing game: {forced_game_name}")
            
            self._last_forced_game = self.forced_game.copy()
            self.forced_game = None
            self.last_game = None
            
            logger.debug("🧹close_fake_executable from stop_force_game")
            self.close_fake_executable()
            
            try:
                if self.rpc:
                    self.rpc.clear()
                    self.rpc.close()
            except Exception:
                pass
            
            self.client_id = "1095416975028650046"  # default Client ID
            self._connect_rpc(self.client_id)
            
            self._force_stop_time = time.time()
            
            logger.info("🔄 Returning to automatic game detection")

    def _disconnect_rpc_temporarily(self):
        try:
            if self.rpc:
                self.rpc.close()
                self.rpc = None
                self._connected_client_id = None
                logger.info("📴 RPC temporarily disconnected (forced game mode active).")
        except Exception as e:
            logger.debug(f"Error disconnecting RPC temporarily: {e}")

    def wait_for_file_release(self, path: Path, timeout: float = 3.0) -> bool:
        start = time.time()
        if not path.exists():
            return True
        while time.time() - start < timeout:
            try:
                with open(path, "rb"):
                    return True
            except PermissionError:
                time.sleep(0.1)
            except Exception:
                return False
        return False

    def close_fake_executable(self):
        try:
            temp_dir_str = str(Path(tempfile.gettempdir()) / "discord_fake_game").lower()
            closed_any = False
            
            if IS_MACOS:
                # On macOS we look for processes running from the temp dir
                for proc in psutil.process_iter(["pid", "exe", "cmdline"]):
                    try:
                        exe = proc.info.get("exe") or ""
                        cmdline = proc.info.get("cmdline") or []
                        # Check if running from our temp dir
                        if temp_dir_str in exe.lower() or any(temp_dir_str in arg.lower() for arg in cmdline):
                             logger.info(f"🛑 Closing fake process (PID {proc.pid})")
                             proc.terminate()
                             try:
                                 proc.wait(timeout=3)
                             except psutil.TimeoutExpired:
                                 proc.kill()
                             closed_any = True
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
            else:
                # Windows and Linux logic (using psutil)
                if self.fake_proc and self.fake_proc.poll() is None:
                    logger.info(f"🛑 Closing fake executable (PID {self.fake_proc.pid})")
                    self.fake_proc.terminate()
                    try:
                        self.fake_proc.wait(timeout=3)
                    except Exception:
                        self.fake_proc.kill()
                    closed_any = True
                for proc in psutil.process_iter(["exe", "pid"]):
                    exe = proc.info.get("exe")
                    if exe and exe.lower().startswith(temp_dir_str):
                        proc.terminate()
                        try:
                            proc.wait(timeout=3)
                        except psutil.TimeoutExpired:
                            proc.kill()
                        closed_any = True
                        
            if closed_any:
                time.sleep(0.35)
                logger.info("✅ Fake executable closed")
                
        except Exception as e:
            logger.error(f"❌ Error closing fake executable: {e}")
        finally:
            self.fake_proc = None
            self.fake_exec_path = None

    def launch_quest_game(self, game_name: str, executable_path: str = None):
        """
        Launches a game in 'Quest Mode', allowing multiple instances.
        Copies dumb.exe with a unique name so it appears distinct (optional) 
        or simply runs multiple processes.
        """
        try:
            import re
            safe_name = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', game_name)
            
            temp_dir = Path(tempfile.gettempdir()) / "discord_quests"
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            # Create a unique executable for this game to avoid conflicts and maybe help identification?
            # Actually, simply running dumb.exe multiple times might work if we don't lock it?
            # But Windows locks running executables. So we need separate copies if we want them to run simultaneously from same file?
            # No, multiple processes can run the same EXE. But `launch_fake_executable` tries to delete/overwrite.
            # So here we should use a unique name per game to avoid collisions with the "main" fake game.
            
            unique_subdir = temp_dir / safe_name
            unique_subdir.mkdir(parents=True, exist_ok=True)
            
            # Use the provided executable path (which might be e.g. "bin/win64/game.exe")
            # We need to recreate the structure inside unique_subdir if it has parents
            target_exe_name = executable_path if executable_path else f"{safe_name}.exe"
            
            if IS_MACOS:
                if not target_exe_name.endswith(".app"):
                     target_exe_name += ".app"
            else:
                if not target_exe_name.lower().endswith(".exe"):
                    target_exe_name += ".exe"

            exec_full_path = unique_subdir / target_exe_name
            
            # Prepare executable
            if IS_MACOS:
                # Reuse MacOS logic from launch_fake_executable roughly
                 dumb_path = BASE_DIR / "tools" / "dumb.app"
                 if exec_full_path.exists():
                     shutil.rmtree(exec_full_path)
                 
                 exec_full_path.parent.mkdir(parents=True, exist_ok=True)
                 
                 if dumb_path.exists():
                     shutil.copytree(dumb_path, exec_full_path)
            else:
                 dumb_path = BASE_DIR / "tools" / "dumb.exe"
                 if not dumb_path.exists():
                     logger.error(f"❌ dumb.exe not found in {dumb_path}")
                     return None

                 # We copy it every time to ensure clean state? Or check existence?
                 # If we update dumb.exe we want new one.
                 if exec_full_path.exists():
                     try:
                         # Try to remove if exists 
                         os.remove(exec_full_path)
                     except:
                         pass
                 
                 exec_full_path.parent.mkdir(parents=True, exist_ok=True)
                 
                 if not exec_full_path.exists():
                     shutil.copy2(dumb_path, exec_full_path)

            # Check if already running for this game?
            # We track in self.active_quests
            for gid, data in self.active_quests.items():
                if data.get('name') == game_name and not data.get('finished'):
                    logger.info(f"Quest already active for {game_name}, restarting timer?")
                    # Optional: Restart timer or ignore?
                    # Let's ignore for now or maybe duplicate?
                    # "put multiple games" -> implies different games.
                    pass

            # Launch
            logger.info(f"🚀 Launching Quest Game: {game_name} ({exec_full_path})")
            
            proc = None
            if IS_MACOS:
                proc = subprocess.Popen(["open", "-n", "-a", str(exec_full_path)])
                # On MacOS `open` returns immediately and doesn't give us the PID of the app easily.
                # `launch_fake_executable` stores `proc` but `open` process exits.
                # Identifying the process on Mac for kill is harder.
                # For now let's focus on Windows/Linux or assume we can find it by name.
            else:
                proc = subprocess.Popen([str(exec_full_path)], cwd=str(exec_full_path.parent))
            
            # Store in active quests
            # Use timestamp as ID or something unique
            game_id = f"{game_name}_{int(time.time())}"
            self.active_quests[game_id] = {
                "name": game_name,
                "proc": proc,
                "exec_path": exec_full_path,
                "start_time": time.time(),
                "finished": False
            }
            logger.info(f"✅ Quest started: {game_name} (id={game_id})")
            return game_id

        except Exception as e:
            logger.error(f"❌ Error launching Quest Game '{game_name}': {e}")
            return None

    def stop_quest_game(self, game_id, keep_in_list=False):
        if game_id in self.active_quests:
            data = self.active_quests[game_id]
            proc = data.get("proc")
            name = data.get("name")
            exec_path = data.get("exec_path")
            logger.info(f"🛑 Stopping Quest: {name}...")
            
            killed = False
            # 1. Try killing via process object (if valid and not macOS 'open' process which exits immediately)
            if proc:
                try:
                    if proc.poll() is None:
                        logger.info(f"🛑 Terminating PID {proc.pid} via object...")
                        proc.terminate()
                        try:
                            proc.wait(timeout=2)
                        except:
                            proc.kill()
                        killed = True
                except Exception as e:
                    logger.warning(f"Error killing quest proc via obj: {e}")
 
            # 2. Force kill by path if we haven't confirmed kill (or for safety)
            # This handles cases where proc object is lost or was a launcher wrapper
            if exec_path and Path(exec_path).exists():
                try:
                    t_path = str(exec_path).lower()
                    for p in psutil.process_iter(['pid', 'exe']):
                        try:
                            pexe = (p.info.get('exe') or "").lower()
                            if pexe == t_path:
                                logger.info(f"🔪 Killing process by path: {pexe} (PID {p.info['pid']})")
                                p.terminate()
                                try:
                                    p.wait(timeout=2)
                                except:
                                    p.kill()
                                killed = True
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            continue
                except Exception as e:
                    logger.error(f"Error killing quest by path: {e}")
            
            if keep_in_list:
                data["finished"] = True
                data["proc"] = None # Released
            else:
                del self.active_quests[game_id]
                logger.info(f"🗑️ Quest removed from list: {name}")

    def check_quests(self):
        """Called periodically to check timers and remove finished processes."""
        if not self.active_quests:
            return

        now = time.time()
        # Iterate over copy
        for gid, data in list(self.active_quests.items()):
            if data.get("finished"):
                continue
                
            start = data.get("start_time", 0)
            elapsed = now - start
            
            if elapsed >= (16 * 60) + 30: # 16 minutes 30 seconds
                logger.info(f"⏰ Quest time completed for {data['name']}.")
                self.stop_quest_game(gid, keep_in_list=True)
            else:
                # Check if process died manually?
                proc = data.get("proc")
                if proc and not IS_MACOS:
                    if proc.poll() is not None:
                        logger.info(f"⚠️ Quest process {data['name']} terminated unexpectedly.")
                        self.stop_quest_game(gid, keep_in_list=True)

    def _create_linux_fake_binary(self, target_path: Path):
        """Create a minimal native Linux ELF-like fake binary that just sleeps."""
        import stat
        script_content = '#!/bin/sh\nexec sleep 86400\n'
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(script_content)
        target_path.chmod(target_path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    def launch_fake_executable(self, executable_path: str):
        try:
            temp_dir = Path(tempfile.gettempdir()) / "discord_fake_game"
            
            if IS_MACOS:
                # On macOS, executable_path might be "Something.app"
                # We expect the user to have placed the .app in tools/ or we use a generic one?
                # The user said: "I already compiled the fake exe on mac and now it is .app"
                # Let's assume we have a "dumb.app" in tools/ similar to "dumb.exe"
                
                app_name = Path(executable_path).name
                if not app_name.endswith(".app"):
                    # If discord asks for "game.exe", we might want to map it to "game.app" or just use a generic "FakeGame.app"
                    # For simplicity, let's copy our generic dumb.app to "FakeGame.app"
                    app_name = "FakeGame.app"
                
                exec_full_path = temp_dir / app_name
                
                # Clean previous if exists
                if exec_full_path.exists():
                    shutil.rmtree(exec_full_path)
                
                exec_full_path.parent.mkdir(parents=True, exist_ok=True)
                
                dumb_path = BASE_DIR / "tools" / "dumb.app"
                if not dumb_path.exists():
                     logger.error(f"❌ dumb.app not found in {dumb_path}")
                     return
 
                # Copy .app bundle
                shutil.copytree(dumb_path, exec_full_path)
                
                logger.info(f"🚀 Running fake app: {exec_full_path}")
                # Open the app using 'open' command
                proc = subprocess.Popen(["open", "-n", "-a", str(exec_full_path)])
                self.fake_proc = proc
                self.fake_exec_path = exec_full_path
                
            elif IS_LINUX:
                # Linux: Create a lightweight native shell script as fake executable
                # No Wine needed! Discord on Linux detects processes by name, not by PE format.
                exe_name = Path(executable_path).stem  # e.g. "forzahorizon4" from "forzahorizon4.exe"
                exec_full_path = temp_dir / exe_name
                exec_full_path.parent.mkdir(parents=True, exist_ok=True)

                if self.fake_exec_path == exec_full_path and self.fake_proc and self.fake_proc.poll() is None:
                    logger.debug(f"🚀 Executable already running: {exec_full_path}")
                    return

                # Create a native Linux fake binary (shell script that sleeps)
                self._create_linux_fake_binary(exec_full_path)

                logger.info(f"🐧 Running fake executable (Native Linux): {exec_full_path}")
                proc = subprocess.Popen(
                    [str(exec_full_path)],
                    cwd=str(exec_full_path.parent),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                self.fake_proc = proc
                self.fake_exec_path = exec_full_path

            else:
                # Windows logic
                exec_full_path = temp_dir / executable_path
                exec_full_path.parent.mkdir(parents=True, exist_ok=True)

                if self.fake_exec_path == exec_full_path and self.fake_proc and self.fake_proc.poll() is None:
                    logger.debug(f"🚀 Executable already running: {exec_full_path}")
                    return
                dumb_path = BASE_DIR / "tools" / "dumb.exe"
                if not dumb_path.exists():
                    logger.error(f"❌ dumb.exe not found in {dumb_path}")
                    return
                if not exec_full_path.exists():
                    shutil.copy2(dumb_path, exec_full_path)
                else:
                    if not self.wait_for_file_release(exec_full_path, timeout=3.0):
                        logger.error(f"❌ The file {exec_full_path} is still locked by another process")
                        return
                logger.info(f"🚀 Running fake executable: {exec_full_path}")
                proc = subprocess.Popen([str(exec_full_path)], cwd=str(exec_full_path.parent))
                self.fake_proc = proc
                self.fake_exec_path = exec_full_path
                
        except Exception as e:
            logger.error(f"❌ Error creating/running fake executable: {e}")

    def _get_http_session(self):
        if self._http_session is None:
            import requests
            self._http_session = requests.Session()
            self._http_session.headers.update({"User-Agent": "GeForcePresence/1.0"})
        return self._http_session

    def _fetch_discord_apps_cached(self, force_download: bool = False):
        try:
            if not force_download and DISCORD_CACHE_PATH.exists():
                data = safe_json_load(DISCORD_CACHE_PATH)
                if data and isinstance(data, dict):
                    ts = data.get("_ts", 0)
                    apps = data.get("apps", [])
                    if apps and (time.time() - ts < DISCORD_CACHE_TTL):
                        # update last apps ts for normalized cache invalidation
                        self._last_apps_ts = ts
                        return apps

            sess = self._get_http_session()
            logger.info("⬇️ Downloading Discord detectable applications list...")
            resp = sess.get(DISCORD_DETECTABLE_URL, stream=True, timeout=15)
            if resp.status_code == 200:
                total_size = int(resp.headers.get('content-length', 0))
                downloaded = 0
                chunks = []
                self.download_progress.emit(0, total_size)
                
                for chunk in resp.iter_content(chunk_size=65536):
                    if chunk:
                        chunks.append(chunk)
                        downloaded += len(chunk)
                        self.download_progress.emit(downloaded, total_size)
                
                self.download_progress.emit(-1, -1) # Signal completion
                
                raw_data = b"".join(chunks)
                apps = json.loads(raw_data)
                
                if apps:
                    to_save = {"_ts": int(time.time()), "apps": apps}
                    try:
                        save_json(to_save, DISCORD_CACHE_PATH)
                        self._last_apps_ts = to_save["_ts"]
                        logger.info(f"✅ Discord cache updated ({len(apps)} apps).")
                    except Exception:
                        pass
                    return apps
                else:
                    logger.warning("⚠️ Discord response does not contain any applications.")
            else:
                logger.warning(f"⚠️ Error downloading from Discord: Status {resp.status_code}")
                self.download_progress.emit(-1, -1)
        except Exception as e:
            logger.debug(f"Error getting detectable from Discord: {e}")
            self.download_progress.emit(-1, -1)
        return []


    def _get_normalized_apps(self):
        apps = self._fetch_discord_apps_cached()
        if not apps:
            return []

        # read ts from file to detect external changes
        try:
            data = safe_json_load(DISCORD_CACHE_PATH) or {}
            ts = data.get("_ts", 0)
        except Exception:
            ts = 0

        with self._apps_lock:
            if self._cached_apps_normalized is None or ts != getattr(self, "_last_apps_ts", None):
                norm = []
                for app in apps:
                    name = app.get("name", "") or ""
                    aliases = app.get("aliases", []) or []
                    n_name = name.lower()
                    n_aliases = [a.lower() for a in aliases if a]
                    norm.append({
                        "original": app,
                        "n_name": n_name,
                        "n_aliases": n_aliases
                    })
                self._cached_apps_normalized = norm
                self._last_apps_ts = ts
        return self._cached_apps_normalized



    def _cheap_prefilter(self, gnl, n_name, n_aliases):
        # fast substring check (cheap)
        if gnl in n_name or any(gnl in a for a in n_aliases):
            return True
        # token intersection (cheap)
        tokens = set(gnl.split())
        if tokens and tokens & set(n_name.split()):
            return True
        return False

    def _find_discord_matches(self, game_name: str, max_candidates: int = 5):
        if not game_name:
            return []

        cache_key = game_name.lower()
        with self._match_cache_lock:
            if cache_key in self._match_cache:
                return self._match_cache[cache_key]

        normalized_apps = self._get_normalized_apps()
        if not normalized_apps:
            return []

        candidates = []
        gnl = cache_key

        logger.debug("🔍 Searching for matches with Discord (optimized)...")

        if fuzz and hasattr(fuzz, "ratio"):
            # rapidfuzz path
            for item in normalized_apps:
                app = item["original"]
                n_name = item["n_name"]
                n_aliases = item["n_aliases"]

                # cheap prefilter
                # cheap prefilter (safe: guard against missing attribute)
                _prefilter = getattr(self, "_cheap_prefilter", None)
                if _prefilter is not None:
                    try:
                        if not _prefilter(gnl, n_name, n_aliases):
                            continue
                    except Exception as _e:
                        logger.debug(f"⚠️ _cheap_prefilter failed: {_e} — ignoring cheap filter and continuing.")
                    # if _prefilter is None, we skip the cheap prefilter and let the fuzzy matching run


                score_name = fuzz.ratio(gnl, n_name) / 100.0
                if gnl in n_name:
                    score_name = max(score_name, 0.7 + 0.3 * (len(gnl) / len(n_name)))
                
                score_alias = 0.0
                if n_aliases:
                    best_alias_score = 0
                    for alias in n_aliases:
                        s = fuzz.ratio(gnl, alias) / 100.0
                        if gnl in alias:
                            s = max(s, 0.7 + 0.3 * (len(gnl) / len(alias)))
                        if s > best_alias_score:
                            best_alias_score = s
                    score_alias = best_alias_score

                score = max(score_name, score_alias)
                if score > 0.35:
                    self._add_candidate(candidates, app, score)

        else:
            # difflib fallback with cheap prefilter
            import difflib as _difflib
            for item in normalized_apps:
                app = item["original"]
                n_name = item["n_name"]
                n_aliases = item["n_aliases"]

                # cheap prefilter (safe: guard against missing attribute)
                _prefilter = getattr(self, "_cheap_prefilter", None)
                if _prefilter is not None:
                    try:
                        if not _prefilter(gnl, n_name, n_aliases):
                            continue
                    except Exception as _e:
                        logger.debug(f"⚠️ _cheap_prefilter failed: {_e} — ignoring cheap filter and continuing.")
                # if _prefilter is None, we skip the cheap prefilter and let the fuzzy matching run


                score_name = _difflib.SequenceMatcher(None, gnl, n_name).ratio()
                if gnl in n_name:
                    score_name = max(score_name, 0.7 + 0.3 * (len(gnl) / len(n_name)))
                    
                score_alias = 0.0
                for a in n_aliases:
                    s = _difflib.SequenceMatcher(None, gnl, a).ratio()
                    if gnl in a:
                        s = max(s, 0.7 + 0.3 * (len(gnl) / len(a)))
                    if s > score_alias:
                        score_alias = s

                score = max(score_name, score_alias)
                if score > 0.35:
                    self._add_candidate(candidates, app, score)

        candidates.sort(key=lambda x: x["score"], reverse=True)
        result = candidates[:max_candidates]

        with self._match_cache_lock:
            # save only top-N to avoid infinite growth
            self._match_cache[cache_key] = result
            # optional: if len(self._match_cache) > 2000: clear or pop oldest -> implement LRU if needed

        return result


    def _add_candidate(self, candidates, app, score):
        exe = None
        
        for e in app.get("executables", []) or []:
            e_os = e.get("os")
            e_name = e.get("name")
            
            if IS_WINDOWS:
                if e_os == "win32" and e_name:
                    exe = e_name
                    break
            elif IS_MACOS:
                if e_os in ["macos", "darwin"] and e_name:
                    exe = e_name
                    break
            elif IS_LINUX:
                if e_os == "linux" and e_name:
                    exe = e_name
                    break
        
        # Fallback: if no platform-specific exe found, use win32 exe name.
        # On Linux/macOS we use this name for Discord matching (the actual binary is a fake shell script).
        if not exe and (IS_MACOS or IS_LINUX):
             for e in app.get("executables", []) or []:
                if e.get("os") == "win32" and e.get("name"):
                    exe = e.get("name")
                    break

        candidates.append({
            "name": app.get("name", ""),
            "id": app.get("id"),
            "exe": exe,
            "score": score,
            "aliases": app.get("aliases", [])
        })

    def _apply_discord_match(self, game_key: str, match: dict):
        try:
            if not match or "id" not in match:
                return False
            config_path = CONFIG_DIR / "games_config_merged.json"
            games_config = safe_json_load(config_path) or {}

            entry = games_config.get(game_key, {}) or {}

            if match.get("exe"):
                current_exe = entry.get("executable_path")
                if not current_exe:
                    entry["executable_path"] = match["exe"]
            
            if match.get("id"):
                current_id = entry.get("client_id")
                if not current_id:
                    entry["client_id"] = match["id"]
            
            games_config[game_key] = entry
            save_json(games_config, config_path)
            self.games_map = games_config
            
            # Update forced_game if it matches
            if self.forced_game and self.forced_game.get("name") == game_key:
                if match.get("id") and not self.forced_game.get("client_id"):
                    self.forced_game["client_id"] = match["id"]
                if match.get("exe") and not self.forced_game.get("executable_path"):
                    self.forced_game["executable_path"] = match["exe"]
                logger.info(f"🔄 Forced game '{game_key}' updated live with Discord data.")

            logger.info(f"✅ Discord match applied for '{game_key}': id={match.get('id')}, exe={match.get('exe')}")
            return True
        except Exception as e:
            logger.error(f"❌ Error applying discord match: {e}")
            return False

    def _ensure_discord_match(self, game_key: str):
        try:
            if not game_key or not game_key.strip():
                return

            # Check attempt limit
            attempts = self._match_attempt_counts.get(game_key, 0)
            if attempts >= 2:
                if attempts == 2:
                    logger.debug(f"🛑 Match attempt limit reached for '{game_key}'. No further searches this session.")
                    self._match_attempt_counts[game_key] = 3 # Avoid log spam
                return

            now = time.time()
            last = self._last_match_attempt.get(game_key, 0)
            if now - last < self.MATCH_ATTEMPT_COOLDOWN:
                logger.debug(f"Skipping Discord match for {game_key}: cooldown active ({now-last:.1f}s).")
                return

            # Mark attempt
            self._last_match_attempt[game_key] = now
            self._match_attempt_counts[game_key] = attempts + 1

            # Check if already in progress
            if game_key in self._ongoing_match_jobs:
                logger.debug(f"Match already in progress for {game_key}")
                return

            # run match in background but mark as ongoing
            def run():
                try:
                    self._ongoing_match_jobs.add(game_key)
                    candidates = self._find_discord_matches(game_key, max_candidates=6)
                    if not candidates:
                        logger.info(f"ℹ️ No Discord matches found for '{game_key}'")
                        return
                        
                    top = candidates[0].copy()
                    
                    # If the best match does not have an executable, look for one with score >= 0.75 that does
                    if not top.get("exe"):
                        for c in candidates[1:]:
                            if c.get("exe") and c.get("score", 0) >= 0.75:
                                # Avoid promoting a different game if the first match was almost exact
                                if top.get("score", 0) >= 0.98 and c.get("score", 0) < 0.98:
                                    logger.info(f"🚫 Did not promote '{c.get('name')}' over '{top.get('name')}' because original match was exact and candidate was not.")
                                    continue
                                
                                # Promote this match as the best, but keeping the original score
                                # so the user isn't prompted if the real name was identical
                                logger.info(f"♻️ Promoted '{c.get('name')}' over '{top.get('name')}' for having an executable.")
                                c_copy = c.copy()
                                c_copy["score"] = top["score"]
                                top = c_copy
                                break

                    if top.get("score", 0) >= DISCORD_AUTO_APPLY_THRESHOLD:
                        applied = self._apply_discord_match(game_key, top)
                        if applied:
                            logger.info(f"🔁 Automatically applied Discord match: {top.get('name')} (score {top.get('score'):.2f})")
                        return
                    self.request_match_selection.emit(game_key, candidates)
                except Exception as e:
                    logger.debug(f"Error in ask_discord_match_for_new_game: {e}")
                finally:
                    self._ongoing_match_jobs.discard(game_key)

            threading.Thread(target=run, daemon=True).start()

        except Exception as e:
            logger.debug(f"Error ensuring discord match: {e}")

    # Slot to receive the selected match from UI
    def on_match_selected(self, game_key: str, match: dict):
        if match:
             self._apply_discord_match(game_key, match)
        else:
             logger.info(f"ℹ️ User ignored Discord match for '{game_key}'")

    def check_presence(self):
        try:
            self.check_quests() # Check optional quests
            
            game = self.find_active_game()
            self.update_presence(game)


        except Exception as e:
            if str(e) not in (
                "'NoneType' object has no attribute 'get'",
                "cannot access local variable 'title' where it is not associated with a value",
            ):
                logger.error(f"❌ Unexpected error in main loop: {e}")
            try:
                if self.rpc: self.rpc.clear()
            except Exception:
                pass
            logger.debug("🧹close_fake_executable from check_presence exception handler")
            self.close_fake_executable()

    def find_active_game(self) -> Optional[dict]:
        try:
            title = None
            
            if IS_WINDOWS:
                if not win32gui:
                    logger.error("win32gui not available")
                    return None
                    
                hwnds = []
                win32gui.EnumWindows(lambda h, p: p.append(h) if win32gui.IsWindowVisible(h) else None, hwnds)
                last_title = getattr(self, "_last_window_title", None)
                
                # OPTIMIZATION: Get GFN PIDs once to avoid instantiating psutil.Process for every visible window
                gef_pids = set()
                try:
                    for proc in psutil.process_iter(['name', 'pid']):
                        if proc.info['name'] and proc.info['name'].lower() == "geforcenow.exe":
                            gef_pids.add(proc.pid)
                except Exception:
                    pass

                for hwnd in hwnds:
                    try:
                        _, pid = win32process.GetWindowThreadProcessId(hwnd)
                        if pid not in gef_pids:
                            continue
                    except Exception:
                        continue
                    title = win32gui.GetWindowText(hwnd)
                    break
            
            elif IS_MACOS:
                # Use AppleScript to get the window title of GeForce NOW
                # We assume the process name is "GeForceNOW" or similar.
                # The AppleScript gets the window 1 of process "GeForceNOW"
                cmd = """
                tell application "System Events"
                    set procName to "GeForceNOW"
                    if exists process procName then
                        try
                            return name of window 1 of process procName
                        on error
                            return ""
                        end try
                    end if
                    return ""
                end tell
                """
                result = subprocess.run(["osascript", "-e", cmd], capture_output=True, text=True)
                if result.returncode == 0:
                    title = result.stdout.strip()

            elif IS_LINUX:
                # Linux: KDE KWin Scripting (Wayland-native) or xdotool (X11)
                if self._linux_detector:
                    try:
                        raw_title = self._linux_detector.get_gfn_window_title()
                        if raw_title:
                            # extract_game_name() handles Turkish ('da), English (on/in), dash formats
                            game_name = self._linux_detector.extract_game_name(raw_title)
                            if game_name:
                                title = raw_title
                                setattr(self, '_linux_game_name', game_name)
                            else:
                                # GFN open but in lobby — no game
                                setattr(self, '_linux_game_name', None)
                                self.log_once("⚠️ GeForce NOW is open but game has not started (lobby/home)")
                                return None
                        else:
                            setattr(self, '_linux_game_name', None)
                    except Exception as e:
                        logger.debug(f"Linux window detection error: {e}")

            if not title:
                self.log_once("⚠️ GeForce NOW is not open (or no active window)")
                return None

            last_title = getattr(self, "_last_window_title", None)
            if title == last_title:
                pass
            else:
                setattr(self, "_last_window_title", title)

            if "Application Launch failed" in title or "Application resource corrupted" in title:
                now = time.time()
                last_time = getattr(self, "_last_gfn_error_time", 0)
                if now - last_time > 60:
                    setattr(self, "_last_gfn_error_time", now)
                    self.gfn_error_detected.emit()
                return None

            # On Linux: game name already extracted cleanly by the detector
            # The Windows regex below would destroy Turkish titles like "GeForce NOW'da OyunAdı"
            if IS_LINUX:
                clean = getattr(self, '_linux_game_name', None)
                if not clean:
                    return None
            else:
                clean = re.sub(r'\s*(en|on|in|via)?\s*GeForce\s*NOW.*$', '', title, flags=re.IGNORECASE).strip()
                clean = re.sub(r'[\u00ae\u2122]', '', clean).strip()
                if not clean:
                    return None

            last_clean = getattr(self, "_last_clean_title", None)
            if clean != last_clean:
                setattr(self, "_last_clean_title", clean)
                logger.info(f"🎮 Detected game: {clean!r}")

            appid = None 
            for game_name, info in self.games_map.items():
                if clean.lower() == game_name.lower():
                    if not info.get("steam_appid"):
                        appid = find_steam_appid_by_name(clean)
                        if appid:
                            info["steam_appid"] = appid
                            config_path = CONFIG_DIR / "games_config_merged.json"
                            games_config = safe_json_load(config_path) or {}
                            games_config.setdefault(game_name, {})
                            games_config[game_name]["steam_appid"] = appid
                            save_json(games_config, config_path)
                            logger.info(f"✅ Steam AppID updated in JSON for: {game_name} -> {appid}")
                            self.games_map = games_config
                    
                    # Check if missing client_id
                    if not info.get("client_id"):
                        try:
                            threading.Thread(
                                target=self._ensure_discord_match,
                                args=(clean,),
                                daemon=True
                            ).start()
                        except Exception as e:
                            logger.debug(f"could not start discord-match thread (update): {e}")

                    # Ensure name is in the returned object
                    info["name"] = game_name
                    return info
            appid = find_steam_appid_by_name(clean)
            new_game = {
                "name": clean,
                "steam_appid": appid,
                "image": "steam"
            }
            self.games_map[clean] = new_game
            config_path = CONFIG_DIR / "games_config_merged.json"
            games_config = safe_json_load(config_path) or {}
            games_config[clean] = new_game
            save_json(games_config, config_path)
            updated = self.games_map.get(clean)
            if updated:
                new_game = updated
            logger.info(f"🆕 Game added to config: {clean} (AppID: {appid})")
            self.games_map = games_config

            try:
                threading.Thread(
                    target=self._ensure_discord_match,
                    args=(clean,),
                    daemon=True
                ).start()
            except Exception as e:
                logger.debug(f"could not start discord-match thread: {e}")
            return new_game

        except Exception as e:
            if str(e) == "cannot access local variable 'title' where it is not associated with a value":
                self.log_once(f"⚠️ GeForce NOW is closed")
            else:
                logger.error(f"⚠️ Error detecting active game: {e}")

    def log_once(self, msg, level="info"):
        if msg != self.last_log_message:
            getattr(logger, level)(msg)
            self.last_log_message = msg

    def is_geforce_running(self) -> bool:
        try:
            for proc in psutil.process_iter(attrs=['name']):
                name = (proc.info.get('name') or "").lower()
                if IS_WINDOWS:
                    if name == "geforcenow.exe":
                        return True
                elif IS_MACOS:
                    # Verify exact process name on macOS
                    if name == "geforcenow": # Likely "GeForceNOW"
                        return True
                elif IS_LINUX:
                    # On Linux, GFN runs via browser or Electron client
                    if 'geforcenow' in name:
                        return True
            # On Linux, also check via window detector
            if IS_LINUX and self._linux_detector:
                return self._linux_detector.is_gfn_running()
        except Exception as e:
            logger.debug(f"Error checking processes: {e}")
        return False
    
    def clear_forced_game(self):
        if self.forced_game:
            logger.info(f"🧹 Forced mode deactivated: {self.forced_game.get('name')}")
            self.forced_game = None

    def update_presence(self, game_info: Optional[dict]):
        if getattr(self, "forced_game", None):
            game_info = self.forced_game
            current_time = time.time()
            if not hasattr(self, "_last_forced_log") or current_time - self._last_forced_log > 300:
                logger.info(f"🔧 Forced mode active: {self.forced_game.get('name')}")
                self._last_forced_log = current_time

        if (hasattr(self, "_force_stop_time") and 
            getattr(self, "_last_forced_game", None) and 
            game_info and 
            game_info.get("name") == self._last_forced_game.get("name")):
            
            current_time = time.time()
            if current_time - self._force_stop_time < 10:
                logger.debug(f"⏸️  Avoiding automatic reconnection to {game_info.get('name')} after stopping forced game")
                try:
                    if self.rpc: self.rpc.clear()
                except Exception:
                    pass
                self.last_game = None
                return

        current_game = game_info or None
        game_changed = not self.is_same_game(self.last_game, current_game)
        
        status, group_size = None, None
        if current_game and current_game.get("steam_appid"):
            status, group_size = self.scraper.get_rich_presence()
        
        if current_game and current_game.get("name") in self.games_map:
            defaults = self.games_map[current_game["name"]]
            merged = {**defaults, **current_game}
            current_game = merged

        # Check if missing client_id and ensure match
        if current_game:
            if not current_game.get("client_id"):
                self._ensure_discord_match(current_game["name"])

        if game_changed:
            logger.info(f"🔍 DEBUG: Game Changed detected.")
            logger.info(f"   OLD: {self.last_game}")
            logger.info(f"   NEW: {current_game}")
            
            logger.debug(f"🧹close_fake_executable from update_presence (game_changed)")
            self.close_fake_executable()
            if current_game and current_game.get("executable_path"):
                self.launch_fake_executable(current_game["executable_path"])
            
            if current_game:
                self.current_game_start_time = int(time.time())

        if not current_game:
            if self.last_game is not None:
                try:
                    if self.rpc: self.rpc.clear()
                except Exception:
                    pass
                self.last_game = None
                self.current_game_start_time = None
            return

        client_id = current_game.get("client_id") or self.client_id
        
        should_change_client = True
        if (hasattr(self, "_force_stop_time") and 
            getattr(self, "_last_forced_game", None) and 
            current_game and 
            current_game.get("name") == self._last_forced_game.get("name")):
            
            current_time = time.time()
            if current_time - self._force_stop_time < 10:
                should_change_client = False
                client_id = self.client_id

        # Determine if we need to connect/reconnect
        # Condition 1: RPC is None (disconnected)
        # Condition 2: Client ID changed and we are allowed to change it
        current_connected_id = getattr(self, "_connected_client_id", None)
        
        if (self.rpc is None) or (current_connected_id != client_id and should_change_client):
            logger.debug(f"🔄 RPC Update needed. Current: {current_connected_id}, Target: {client_id}, RPC Object: {self.rpc is not None}")
            try:
                if self.rpc:
                    self.rpc.clear()
                    self.rpc.close()
            except Exception:
                pass
            
            if client_id:
                self._connect_rpc(client_id)
                if current_connected_id != client_id:
                    self.log_once(f"🔁 Changed client_id to {client_id}")
                else:
                    self.log_once(f"🔁 Reconnected client_id {client_id}")

        def split_status(s):
            for sep in ["|", " - ", ":", "›", ">"]:
                if sep in s:
                    a, b = s.split(sep, 1)
                    return a.strip(), b.strip()
            return s.strip(), None

        # Determine Max Size settings first to decide how to format text
        max_size_setting = current_game.get("max_party_size")
        
        # Default behavior: Split status
        details, state = (split_status(status) if status else (None, None))
        party_size_data = None

        if max_size_setting:
            try:
                max_size = int(max_size_setting)
                # If custom party size is active, we avoid splitting to prevent "Status (1 of 4)" weirdness
                # We put the full status in details
                details = status
                
                if max_size == 1:
                    state = self.texts.get("playing_solo", "Playing solo")
                    party_size_data = [1, 1]
                else:
                    # Generic state for group if we moved real status to details
                    state = self.texts.get("playing_in_group", "Playing in Group")
                    # Use scraper group_size if available, else 1
                    current_size = group_size if group_size else 1
                    party_size_data = [current_size, max_size]

            except ValueError:
                pass

        # If NO custom max_size, use legacy logic for scraper-detected groups
        elif group_size is not None:
             # If scraper found a group but no custom max size set
             if group_size == 1:
                 state = self.texts.get("playing_solo", "Playing solo")
             else:
                 state = self.texts.get("playing_in_group", "On a Group")
             # We can optionally add party_size here if we want to show (? of ?) but usually scraper only gives current.
             # If we want to show size for scraped groups, we need a max.
             if current_game.get("party_size"):
                 party_size_data = current_game.get("party_size")
        
        # Legacy/Alternative party_size key fallback
        if not party_size_data and current_game.get("party_size"):
             party_size_data = current_game.get("party_size")

        # ---- CUSTOM PRESENCE FALLBACK ----
        # Use custom values only if real Steam/Scraper data is missing
        custom_details = current_game.get("custom_details")
        custom_state = current_game.get("custom_state")
        c_party_curr = current_game.get("custom_party_size_current", 0)
        c_party_max = current_game.get("custom_party_size_max", 0)

        # Check existing data from scraper/defaults
        has_real_details = (details is not None and len(details.strip()) > 0)
        has_real_state = (state is not None and len(state.strip()) > 0)
        
        # If no real details, check custom
        if not has_real_details and custom_details is not None and len(str(custom_details).strip()) > 0:
            details = str(custom_details)
            has_real_details = True
        
        # If no real state, check custom
        if not has_real_state and custom_state is not None and len(str(custom_state).strip()) > 0:
            state = str(custom_state)
            has_real_state = True

        # ---- AUTOMATIC PRESETS FALLBACK ----
        # Only apply presets for non-Steam games (Epic, Ubisoft, etc.) to prevent "kolpa" (fake) details
        # for Steam games when the real-time scraper is offline or not logged in.
        is_steam_game = bool(current_game.get("steam_appid"))
        if not is_steam_game and (not has_real_details or not has_real_state):
            preset_details, preset_state = get_preset(current_game.get("name", ""))
            if not has_real_details:
                details = preset_details
            if not has_real_state:
                state = preset_state
            
        # Party Size Logic:
        # Steam/Scraper usually provides Group Size (Current) but not Max.
        # Custom Presence provides Max (and optionally Current).
        # We combine them: [Scraped_Current or Custom_Current, Custom_Max]
        
        final_current = group_size if group_size else c_party_curr
        # Note: If group_size is None, c_party_curr defaults to 0. 
        # If group_size is 0, we treat it as 0.
        
        if c_party_max > 0:
            # We have a valid max size from Custom Presence
            # Even if current is 0, we might want to show "0 of 5" or "1 of 5"?
            # Usually min is 1. But let's trust the values.
            # If scraper current is None, use custom current.
            # If scraper current is valid, use it.
            party_size_data = [final_current, c_party_max]
        elif party_size_data:
            # If we have existing party_size_data from scraper (e.g. [1, 4]) use it.
            pass
        elif c_party_curr > 0 and c_party_max > 0:
             # Fallback if logic above missed it
             party_size_data = [c_party_curr, c_party_max]

        # Restore ignore check
        rn = (current_game.get('name') or '').strip().lower()
        if rn in ["geforce now", "games", ""]:
            try:
                if self.rpc: self.rpc.clear()
            except:
                pass
            self.last_game = None
            return

        presence_data = {
            "details": details,
            "state": state,
            "large_image": current_game.get('image', 'steam'),
            "large_text": current_game.get('name'),
            "small_image": current_game.get("icon_key") if current_game.get("icon_key") else None,
            "start": self.current_game_start_time
        }
        
        if party_size_data:
            presence_data["party_size"] = party_size_data

        try:
            if self.rpc:
                self.rpc.update(**{k: v for k, v in presence_data.items() if v})
        except Exception as e:
            msg = str(e).lower()
            logger.error(f"❌ Error updating Presence: {e}")
            if "pipe was closed" in msg or "socket.send()" in msg:
                try:
                    time.sleep(5) 
                    self._connect_rpc(client_id)
                    logger.info("🔁 Reconnected with Discord RPC after socket error")
                except Exception as e2:
                    logger.error(f"❌ Failed to reconnect to Discord RPC: {e2}")

        self.last_game = dict(current_game) if isinstance(current_game, dict) else current_game
        
        if (hasattr(self, "_force_stop_time") and 
            time.time() - self._force_stop_time >= 10):
            if hasattr(self, "_last_forced_game"):
                del self._last_forced_game
            if hasattr(self, "_force_stop_time"):
                del self._force_stop_time

    def is_same_game(self, g1: Optional[dict], g2: Optional[dict]) -> bool:
        if g1 is None and g2 is None:
            return True
        if (g1 is None) != (g2 is None):
            return False
        for k in ("client_id", "executable_path", "name"):
            if g1.get(k) != g2.get(k):
                return False
        return True
    

    def set_custom_presence(self, data: dict):
        """
        Sets persistent custom presence data for the currently active (or forced) game.
        Keys: custom_details, custom_state, custom_party_size_current, custom_party_size_max
        """
        game = self.forced_game or self.last_game
        if not game:
            return False
            
        game_key = game.get("name")
        if not game_key:
            return False
            
        # Update memory map
        if game_key in self.games_map:
            self.games_map[game_key].update(data)
        
        # Update configuration file
        config_path = CONFIG_DIR / "games_config_merged.json"
        games_config = safe_json_load(config_path) or {}
        
        if game_key in games_config:
            games_config[game_key].update(data)
        else:
            games_config[game_key] = data
            
        save_json(games_config, config_path)
        logger.info(f"✏️ Custom Presence updated for {game_key}: {data}")
    
        # Update the forced game or the last game
        if self.forced_game:
            self.forced_game.update(data)
        if self.last_game:
            self.last_game.update(data)
            
        self.update_presence(game) # Pasa el objeto
        return True

    def close(self):
        if self.rpc:
            try:
                self.rpc.clear()
                self.rpc.close()
                time.sleep(0.1) 
                self._connected_client_id = None
                logger.debug("🧹close_fake_executable from close")
                self.close_fake_executable()
                logger.info("🔴 Discord RPC closed successfully.")
            except Exception:
                pass
