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
from src.core.utils import safe_json_load, save_json, CONFIG_DIR, BASE_DIR, DISCORD_CACHE_PATH, DISCORD_DETECTABLE_URL, DISCORD_CACHE_TTL, DISCORD_AUTO_APPLY_THRESHOLD, DISCORD_ASK_TIMEOUT, IS_WINDOWS, IS_MACOS, IS_LINUX, validate_discord_cache, download_from_github
from src.core.steam_scraper import SteamScraper, find_steam_appid_by_name
from src.core.cookie_manager import CookieManager

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
    presence_updated = pyqtSignal(str, str, bool, bool)
    
    def __init__(self, client_id: str, games_map: dict, cookie_manager: CookieManager, test_rich_url: str, texts: Dict,
                 config_manager=None, update_interval: int = 10, keep_alive: bool = False):
        super().__init__()
        self.config_manager = config_manager
        # en __init__
        self._match_cache_lock = threading.Lock()
        self._apps_lock = threading.Lock()

        # para evitar doble trabajo
        self._ongoing_match_jobs = set()          # juegos con match en progreso
        self._last_match_attempt = {}             # {game_key: timestamp}
        self._match_attempt_counts = {}           # {game_key: count}
        self.MATCH_ATTEMPT_COOLDOWN = 60         # segundos entre intentos para mismo juego

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
        self._is_connecting = False
        
        self.active_quests = {} # {game_id: {proc: Popen, start_time: ts, name: str, finished: bool}}
        
        self.scraper = SteamScraper(self.cookie_manager.env_cookie, test_rich_url)

        self.last_game = None
        self.forced_game = None
        self._last_forced_game = None

        self._force_stop_time = 0
        self.current_game_start_time = None
        
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

        # Connection status tracking
        self.is_online = True
        self._offline_ticks = 0

    def cleanup_all_fake_processes(self):
        """
        Kill any process running from the temp directories:
        - discord_fake_game
        - discord_quests
        """
        logger.info("🧹 Limpiando procesos fake residuales...")
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
                        logger.info(f"🔪 Matando proceso residual: {proc.info['name']} (PID {proc.pid})")
                        proc.terminate()
                        try:
                            proc.wait(timeout=2)
                        except psutil.TimeoutExpired:
                            proc.kill()
                        count += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                     continue
        except Exception as e:
            logger.error(f"Error en limpieza inicial: {e}")
        
        if count > 0:
            logger.info(f"✅ Se limpiaron {count} procesos residuales.")
        else:
            logger.info("✅ No se encontraron procesos residuales.")

    def update_cookie(self, new_cookie: str):
        if new_cookie:
            self.cookie_manager.env_cookie = new_cookie
            self.scraper.set_cookie(new_cookie)
            logger.info("🍪 Cookie actualizada en PresenceManager y Scraper.")
        
    def start_monitoring(self):
        logger.info("🟢 Iniciando monitor de presencia...")
        self.timer.start(self.update_interval * 1000)

        # Solo iniciar sync si hay juegos con falta de datos y tras 5s para dejar iniciar la app
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
            if not validate_discord_cache(data):
                return {"status": "ERROR", "hours": 0}
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
        Recorre todos los juegos en la configuración y, si faltan datos (client_id, executable_path),
        intenta buscarlos en el caché de Discord.
        """
        logger.info(f"🔄 Iniciando sincronización masiva de juegos con Discord (Force={force_download})...")
        self._cancel_sync_flag = False
        try:
            apps = self._fetch_discord_apps_cached(force_download=force_download)
            if not apps:
                logger.warning("⚠️ No hay caché de Discord disponible para sync.")
                # Force download if cache is empty/missing
                apps = self._fetch_discord_apps_cached(force_download=True)
                if not apps:
                     self.sync_error.emit("No se pudo obtener la lista de aplicaciones de Discord.")
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
                 self.sync_progress.emit(processed, total_games, updated_count, "Calculando...")
                 
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
                        logger.info("🛑 Sincronización cancelada por el usuario.")
                        break
                        
                    with progress_lock:
                        processed += 1
                        if result:
                            key, val = result
                            games_to_update[key] = val
                            updated_count += 1
                            if updated_count % 10 == 0:
                                logger.debug(f"Sync progreso: {updated_count} juegos actualizados...")
                        
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
                                eta_str = "Calculando..."
                            
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
                logger.info(f"✅ Sincronización completada: {updated_count} juegos actualizados con datos de Discord.")
            else:
                logger.info("✅ Sincronización completada: No se requirieron actualizaciones.")
            
            self.sync_finished.emit(updated_count, total_games)

        except Exception as e:
            logger.error(f"❌ Error en sincronización masiva: {e}")
            self.sync_error.emit(str(e))

    def stop_monitoring(self):
        self.timer.stop()
        self.close()

    def _connect_rpc(self, client_id: Optional[str] = None):
        client_id = client_id or self.client_id
        
        # Check if we should ignore the default lobby client ID
        if client_id == "1095416975028650046":
            show_lobby = True
            if self.config_manager:
                show_lobby = self.config_manager.get_setting("show_lobby_status", True)
            if not show_lobby:
                logger.debug("Saltando conexión a client_id del Lobby (show_lobby_status deshabilitado).")
                return

        if self._is_connecting:
            logger.debug("Ya hay un intento de conexión en progreso a Discord RPC, saltando intento concurrente.")
            return
        
        self._is_connecting = True
        
        def perform_connect():
            nonlocal client_id
            try:
                if self.rpc:
                    try:
                        self.rpc.close()
                    except Exception:
                        pass
                self.rpc = Presence(client_id)
                
                # Intentar conectar cada 2 segundos por un máximo de 10 segundos (5 intentos)
                max_retries = 5
                retry_delay = 2.0
                
                for attempt in range(max_retries):
                    try:
                        self.rpc.connect()
                        self._connected_client_id = client_id
                        logger.info(f"✅ Conectado a Discord RPC con client_id={client_id}")
                        return
                    except Exception as e:
                        err_str = str(e)
                        is_discord_not_running = "Could not find Discord" in err_str or "Discord installed and running" in err_str
                        
                        if is_discord_not_running and attempt < max_retries - 1:
                            logger.info(f"Discord no parece estar listo aún. Reintentando conexión en {retry_delay}s... (Intento {attempt+1}/{max_retries})")
                            time.sleep(retry_delay)
                        else:
                            raise e
            except Exception as e:
                err_str = str(e)
                if "Could not find Discord" in err_str or "Discord installed and running" in err_str:
                    logger.error(f"💨 No se pudo conectar a Discord RPC tras varios intentos. Relanzando Discord...")
                    AppLauncher.launch_discord()
                else:
                    logger.error(f"❌ Error conectando a Discord RPC: {e}")
                self.rpc = None
                self._connected_client_id = None
            finally:
                self._is_connecting = False

        threading.Thread(target=perform_connect, daemon=True).start()

    def stop_force_game(self):
        """Detiene el forzado de juego y vuelve a la detección automática"""
        if self.forced_game:
            forced_game_name = self.forced_game.get('name', 'Unknown')
            logger.info(f"🧹 Deteniendo forzado de juego: {forced_game_name}")
            
            self._last_forced_game = self.forced_game.copy()
            self.forced_game = None
            self.last_game = None
            
            logger.debug("🧹close_fake_executable desde stop_force_game")
            self.close_fake_executable()
            
            try:
                if self.rpc:
                    self.rpc.clear()
                    self.rpc.close()
            except Exception:
                pass
            
            self.client_id = "1095416975028650046"  # Client ID por defecto
            self._connect_rpc(self.client_id)
            
            self._force_stop_time = time.time()
            
            logger.info("🔄 Volviendo a detección automática de juegos")

    def _disconnect_rpc_temporarily(self):
        try:
            if self.rpc:
                self.rpc.close()
                self.rpc = None
                self._connected_client_id = None
                logger.info("📴 RPC desconectado temporalmente (modo forzar juego activo).")
        except Exception as e:
            logger.debug(f"Error al desconectar RPC temporalmente: {e}")

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
                             logger.info(f"🛑 Cerrando proceso falso (PID {proc.pid})")
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
                    logger.info(f"🛑 Cerrando ejecutable falso (PID {self.fake_proc.pid})")
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
                logger.info("✅ Ejecutable falso cerrado")
                
        except Exception as e:
            logger.error(f"❌ Error cerrando ejecutable falso: {e}")
        finally:
            self.fake_proc = None
            self.fake_exec_path = None

    def launch_quest_game(self, game_name: str, executable_path: str = None):
        """
        Lanza un juego en 'Quest Mode', permitiendo múltiples instancias.
        Copia dumb.exe con un nombre único para que aparezca distinto (opcional) 
        o simplemente corre múltiples procesos.
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
                 dumb_path = BASE_DIR / "tools" / "dumb.app"
                 if not dumb_path.exists():
                     logger.warning("⚠️ dumb.app no encontrado en tools/ (no compilado aún). Se omitirá la Quest en macOS.")
                     return None
                 
                 if exec_full_path.exists():
                     shutil.rmtree(exec_full_path)
                 
                 exec_full_path.parent.mkdir(parents=True, exist_ok=True)
                 shutil.copytree(dumb_path, exec_full_path)
            else:
                 dumb_path = BASE_DIR / "tools" / "dumb.exe"
                 if not dumb_path.exists():
                     logger.error(f"❌ dumb.exe no encontrado en {dumb_path}")
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
                    logger.info(f"Quest ya activa para {game_name}, reiniciando timer?")
                    # Optional: Restart timer or ignore?
                    # Let's ignore for now or maybe duplicate?
                    # "poner multiples juegos" -> implies different games.
                    pass

            # Launch
            logger.info(f"🚀 Iniciando Quest Game: {game_name} ({exec_full_path})")
            
            proc = None
            if IS_MACOS:
                proc = subprocess.Popen(["open", "-n", "-a", str(exec_full_path)])
                # On MacOS `open` returns immediately and doesn't give us the PID of the app easily.
                # `launch_fake_executable` stores `proc` but `open` process exits.
                # Identifying the process on Mac for kill is harder.
                # For now let's focus on Windows/Linux or assume we can find it by name.
            else:
                proc = subprocess.Popen([str(exec_full_path)], cwd=str(exec_full_path.parent))
                self._rename_process_windows(proc.pid, game_name)
            
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
            logger.info(f"✅ Quest iniciada: {game_name} (id={game_id})")
            return game_id

        except Exception as e:
            logger.error(f"❌ Error lanzando Quest Game '{game_name}': {e}")
            return None

    def stop_quest_game(self, game_id, keep_in_list=False):
        if game_id in self.active_quests:
            data = self.active_quests[game_id]
            proc = data.get("proc")
            name = data.get("name")
            exec_path = data.get("exec_path")
            
            logger.info(f"🛑 Deteniendo Quest: {name}...")
            
            killed = False
            # 1. Try killing via process object (if valid and not macOS 'open' process which exits immediately)
            if proc:
                try:
                    if proc.poll() is None:
                        logger.info(f"🛑 Terminando PID {proc.pid} via objeto...")
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
                                logger.info(f"🔪 Matando proceso por path: {pexe} (PID {p.info['pid']})")
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
                logger.info(f"🗑️ Quest eliminada de la lista: {name}")

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
                logger.info(f"⏰ Tiempo de Quest completado para {data['name']}.")
                self.stop_quest_game(gid, keep_in_list=True)
            else:
                # Check if process died manually?
                proc = data.get("proc")
                if proc and not IS_MACOS:
                    if proc.poll() is not None:
                        logger.info(f"⚠️ Proceso de Quest {data['name']} terminó inesperadamente.")
                        self.stop_quest_game(gid, keep_in_list=True)

    def launch_fake_executable(self, executable_path: str, game_name: str = None):
        try:
            temp_dir = Path(tempfile.gettempdir()) / "discord_fake_game"
            
            if IS_MACOS:
                # On macOS, executable_path might be "Something.app"
                # We expect the user to have placed the .app in tools/ or we use a generic one?
                # The user said: "el fake exe ya lo compilé en mac y ahora es .app"
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
                     logger.warning("⚠️ dumb.app no encontrado en tools/ (no compilado aún). Se omitirá iniciar el ejecutable falso en macOS.")
                     return
 
                # Copy .app bundle
                shutil.copytree(dumb_path, exec_full_path)
                
                logger.info(f"🚀 Ejecutando fake app: {exec_full_path}")
                # Open the app using 'open' command
                proc = subprocess.Popen(["open", "-n", "-a", str(exec_full_path)])
                self.fake_proc = proc
                self.fake_exec_path = exec_full_path
                
            else:
                # Windows and Linux logic
                exec_full_path = temp_dir / executable_path
                exec_full_path.parent.mkdir(parents=True, exist_ok=True)

                if self.fake_exec_path == exec_full_path and self.fake_proc and self.fake_proc.poll() is None:
                    logger.debug(f"🚀 Ejecutable ya en ejecución: {exec_full_path}")
                    return
                dumb_path = BASE_DIR / "tools" / "dumb.exe"
                if not dumb_path.exists():
                    logger.error(f"❌ dumb.exe no encontrado en {dumb_path}")
                    return
                if not exec_full_path.exists():
                    shutil.copy2(dumb_path, exec_full_path)
                else:
                    if not self.wait_for_file_release(exec_full_path, timeout=3.0):
                        logger.error(f"❌ El archivo {exec_full_path} sigue bloqueado por otro proceso")
                        return
                logger.info(f"🚀 Ejecutando ejecutable falso: {exec_full_path}")
                proc = subprocess.Popen([str(exec_full_path)], cwd=str(exec_full_path.parent))
                self.fake_proc = proc
                self.fake_exec_path = exec_full_path
                if game_name:
                    self._rename_process_windows(proc.pid, game_name)
                
        except Exception as e:
            logger.error(f"❌ Error creando/ejecutando ejecutable falso: {e}")

    def _rename_process_windows(self, pid: int, title: str):
        """
        Busca las ventanas asociadas a un PID en Windows y cambia su título al del juego.
        Se ejecuta en un hilo secundario y permanece activo mientras el proceso esté vivo,
        renombrando cualquier ventana nueva o existente de dicho PID al título del juego.
        """
        if not IS_WINDOWS or not win32gui or not win32process:
            return

        def rename_thread():
            logger.debug(f"🏷️ Buscando ventanas del proceso {pid} para renombrar a '{title}'...")
            try:
                proc = psutil.Process(pid)
            except Exception:
                return

            while True:
                try:
                    # Verificar si el proceso sigue vivo
                    if not proc.is_running() or proc.status() == psutil.STATUS_ZOMBIE:
                        break
                    
                    hwnds = []
                    win32gui.EnumWindows(lambda h, p: p.append(h), hwnds)
                    
                    for hwnd in hwnds:
                        if win32gui.IsWindow(hwnd):
                            _, win_pid = win32process.GetWindowThreadProcessId(hwnd)
                            if win_pid == pid:
                                current_text = win32gui.GetWindowText(hwnd)
                                if current_text != title:
                                    win32gui.SetWindowText(hwnd, title)
                                    logger.info(f"🏷️ Título de ventana (HWND {hwnd}) para PID {pid} cambiado de '{current_text}' a '{title}'")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    break
                except Exception as e:
                    logger.debug(f"Error al intentar cambiar el título de ventana para PID {pid}: {e}")
                time.sleep(0.5)

        threading.Thread(target=rename_thread, daemon=True).start()

    def _get_http_session(self):
        if self._http_session is None:
            import requests
            self._http_session = requests.Session()
            self._http_session.headers.update({"User-Agent": "GeForcePresence/1.0"})
        return self._http_session

    def _fetch_discord_apps_cached(self, force_download: bool = False):
        backup_path = CONFIG_DIR / "discord_apps_cache_backup.json"
        
        try:
            # 1. Intentar cargar archivo de caché principal si no forzamos descarga y no ha expirado
            if not force_download and DISCORD_CACHE_PATH.exists():
                data = safe_json_load(DISCORD_CACHE_PATH)
                if validate_discord_cache(data):
                    ts = data.get("_ts", 0)
                    apps = data.get("apps", [])
                    if apps and (time.time() - ts < DISCORD_CACHE_TTL):
                        self._last_apps_ts = ts
                        # Si no existe la copia de respaldo, crearla
                        if not backup_path.exists():
                            save_json(data, backup_path)
                        return apps

            # 2. Determinar orden de descarga según si es actualización automática o forzada por el usuario
            apps = []
            download_success = False
            github_url = "https://raw.githubusercontent.com/KarmaDevz/GeForce-NOW-Rich-Presence/master/config/discord_apps_cache.json"
            
            # Si se fuerza la descarga (solicitada manualmente por el usuario/desarrollador),
            # le damos prioridad a Discord para obtener los datos más recientes de la API oficial.
            # Si es una descarga automática en segundo plano (cache expirada), priorizamos GitHub para ahorrar rate-limit y velocidad.
            if force_download:
                sources = [("DISCORD API", DISCORD_DETECTABLE_URL), ("GITHUB", github_url)]
            else:
                sources = [("GITHUB", github_url), ("DISCORD API", DISCORD_DETECTABLE_URL)]

            for source_name, url in sources:
                try:
                    sess = self._get_http_session()
                    if source_name == "GITHUB":
                        logger.info("⬇️ Descargando lista de aplicaciones desde GitHub (Caché en la nube)...")
                    else:
                        logger.info("⬇️ Descargando lista de aplicaciones detectables desde la API de Discord...")
                        
                    resp = sess.get(url, stream=True, timeout=15)
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
                        
                        self.download_progress.emit(-1, -1) # Completado
                        
                        raw_data = b"".join(chunks)
                        loaded_data = json.loads(raw_data)
                        
                        if source_name == "GITHUB":
                            if validate_discord_cache(loaded_data):
                                apps = loaded_data.get("apps", [])
                                # Usamos el tiempo actual en lugar del estático del JSON de GitHub
                                # para evitar un bucle de expiración infinita en el cliente.
                                ts = int(time.time())
                                source_type = "github"
                                download_success = True
                            else:
                                logger.warning("⚠️ El caché descargado de GitHub no es válido.")
                        else: # DISCORD API
                            if isinstance(loaded_data, list) and len(loaded_data) > 0:
                                apps = loaded_data
                                ts = int(time.time())
                                source_type = "discord"
                                download_success = True
                            else:
                                logger.warning("⚠️ La respuesta de Discord no contiene aplicaciones válidas.")
                                
                        if download_success:
                            to_save = {"_ts": ts, "source": source_type, "apps": apps}
                            save_json(to_save, DISCORD_CACHE_PATH)
                            save_json(to_save, backup_path)
                            self._last_apps_ts = to_save["_ts"]
                            logger.info(f"✅ Caché de Discord actualizado desde {source_name} ({len(apps)} apps).")
                            break
                    else:
                        logger.warning(f"⚠️ Error descargando de {source_name}: Status {resp.status_code}")
                except Exception as err:
                    logger.warning(f"⚠️ Falló la descarga desde {source_name}: {err}")

            if not download_success:
                # Si fallaron las descargas de red, emitir fin de barra de progreso
                self.download_progress.emit(-1, -1)

            if download_success:
                return apps

            # --- CAPA DE FALLBACKS LOCALES (SI TODO FALLÓ) ---
            logger.info("🔄 Iniciando capa de fallbacks locales para el caché de Discord...")

            # Fallback local 1: Usar caché local existente (aunque esté expirada)
            if DISCORD_CACHE_PATH.exists():
                data = safe_json_load(DISCORD_CACHE_PATH)
                if validate_discord_cache(data):
                    logger.info("ℹ️ Usando caché local existente (vencido pero válido).")
                    if not backup_path.exists():
                        save_json(data, backup_path)
                    self._last_apps_ts = data.get("_ts", 0)
                    return data.get("apps", [])

            # Fallback local 2: Cargar copia de respaldo local (backup_path)
            if backup_path.exists():
                backup_data = safe_json_load(backup_path)
                if validate_discord_cache(backup_data):
                    logger.info("ℹ️ Cargando copia de respaldo local (backup) para Discord.")
                    save_json(backup_data, DISCORD_CACHE_PATH)
                    self._last_apps_ts = backup_data.get("_ts", 0)
                    return backup_data.get("apps", [])

        except Exception as e:
            logger.error(f"❌ Error crítico en _fetch_discord_apps_cached: {e}")
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



    ROMAN_NUMERALS = {
        'i': 1, 'ii': 2, 'iii': 3, 'iv': 4, 'v': 5,
        'vi': 6, 'vii': 7, 'viii': 8, 'ix': 9, 'x': 10,
        'xi': 11, 'xii': 12, 'xiii': 13, 'xiv': 14, 'xv': 15, 'xvi': 16,
        'xvii': 17, 'xviii': 18, 'xix': 19, 'xx': 20
    }

    def _extract_numbers_and_sequels(self, text: str) -> List[int]:
        if not text:
            return []
        tokens = re.findall(r'\b[a-zA-Z0-9]+\b', text.lower())
        nums = []
        for i, t in enumerate(tokens):
            if t.isdigit():
                nums.append(int(t))
            elif t in self.ROMAN_NUMERALS:
                if t != 'i' or (len(tokens) > 1 and i == len(tokens) - 1):
                    nums.append(self.ROMAN_NUMERALS[t])
        return nums

    def _calculate_string_similarity(self, s1: str, s2: str, is_rapidfuzz: bool = False) -> float:
        if not s1 or not s2:
            return 0.0
        if is_rapidfuzz and fuzz and hasattr(fuzz, "ratio"):
            base_score = fuzz.ratio(s1, s2) / 100.0
        else:
            import difflib as _difflib
            base_score = _difflib.SequenceMatcher(None, s1, s2).ratio()

        if s1 in s2:
            base_score = max(base_score, 0.7 + 0.3 * (len(s1) / len(s2)))
        elif s2 in s1:
            base_score = max(base_score, 0.7 + 0.3 * (len(s2) / len(s1)))

        # Penalización estricta por discrepancia de números/secuelas en el título
        n1 = self._extract_numbers_and_sequels(s1)
        n2 = self._extract_numbers_and_sequels(s2)

        if n1 and n2:
            if n1 != n2:
                # Números explícitamente distintos (ej: MW4 vs MW2, Dark Souls III vs II)
                base_score = min(base_score * 0.4, 0.45)
        elif n1 or n2:
            # Uno tiene número de secuela (>=2) y el otro no (ej: Portal 2 vs Portal)
            active = n1 or n2
            if any(n >= 2 for n in active):
                base_score = min(base_score, 0.70)

        return base_score

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
        use_rapidfuzz = bool(fuzz and hasattr(fuzz, "ratio"))

        logger.debug("🔍 Buscando coincidencias con Discord (optimizado)...")

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
                    logger.debug(f"⚠️ _cheap_prefilter falló: {_e} — ignorando filtro barato y continuando.")

            score_name = self._calculate_string_similarity(gnl, n_name, is_rapidfuzz=use_rapidfuzz)

            score_alias = 0.0
            if n_aliases:
                best_alias_score = 0.0
                for alias in n_aliases:
                    s = self._calculate_string_similarity(gnl, alias, is_rapidfuzz=use_rapidfuzz)
                    if s > best_alias_score:
                        best_alias_score = s
                score_alias = best_alias_score

            score = max(score_name, score_alias)
            if score > 0.35:
                self._add_candidate(candidates, app, score)

        candidates.sort(key=lambda x: x["score"], reverse=True)
        result = candidates[:max_candidates]

        with self._match_cache_lock:
            # guarda solo top-N para evitar crecimiento infinito
            self._match_cache[cache_key] = result
            # opcional: if len(self._match_cache) > 2000: clear or pop oldest -> implement LRU if needed

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
        
        # Fallback check for macOS if no mac exe found (sometimes they are listed as win32 but usable via Wine/Crossover?)
        # Or maybe the user logic intended to grab win32 exe name as fallback?
        if not exe and IS_MACOS:
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

            logger.info(f"✅ Discord match aplicado para '{game_key}': id={match.get('id')}, exe={match.get('exe')}")
            return True
        except Exception as e:
            logger.error(f"❌ Error aplicando discord match: {e}")
            return False

    def _ensure_discord_match(self, game_key: str):
        try:
            if not game_key or not game_key.strip():
                return

            # Check attempt limit
            attempts = self._match_attempt_counts.get(game_key, 0)
            if attempts >= 2:
                if attempts == 2:
                    logger.debug(f"🛑 Límite de intentos de match alcanzado para '{game_key}'. No se buscará más en esta sesión.")
                    self._match_attempt_counts[game_key] = 3 # Evitar spam en el log
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
                        # Si no hay candidatos, podría ser un juego muy nuevo no incluido en el caché de GitHub.
                        # Verificamos si la caché actual vino de GitHub; si es así, forzamos la descarga desde la API
                        # de Discord una sola vez (esto cambiará el origen a 'discord' en el JSON y evitará reintentos).
                        cache_data = safe_json_load(DISCORD_CACHE_PATH) or {}
                        if cache_data.get("source", "github") == "github":
                            logger.info(f"🔍 '{game_key}' no encontrado en el caché de GitHub. Buscando en la API oficial de Discord...")
                            apps = self._fetch_discord_apps_cached(force_download=True)
                            if apps:
                                candidates = self._find_discord_matches(game_key, max_candidates=6)

                    if not candidates:
                        logger.info(f"ℹ️ No se encontraron matches en Discord para '{game_key}'")
                        return
                        
                    top = candidates[0].copy()
                    
                    # Si el mejor match no tiene ejecutable, buscar uno con score >= 0.75 que sí tenga
                    if not top.get("exe"):
                        for c in candidates[1:]:
                            if c.get("exe") and c.get("score", 0) >= 0.75:
                                # Evitar promover un juego diferente si el primer match era casi exacto
                                if top.get("score", 0) >= 0.98 and c.get("score", 0) < 0.98:
                                    logger.info(f"🚫 No se promovió '{c.get('name')}' sobre '{top.get('name')}' porque el match original era exacto y el candidato no.")
                                    continue
                                
                                # Promover este match como el mejor, pero con el score del original
                                # para que no se pregunte al usuario si el nombre real era idéntico
                                logger.info(f"♻️ Se promovió '{c.get('name')}' sobre '{top.get('name')}' por tener ejecutable.")
                                c_copy = c.copy()
                                c_copy["score"] = top["score"]
                                top = c_copy
                                break

                    if top.get("score", 0) >= DISCORD_AUTO_APPLY_THRESHOLD:
                        applied = self._apply_discord_match(game_key, top)
                        if applied:
                            logger.info(f"🔁 Aplicado automaticamente match Discord: {top.get('name')} (score {top.get('score'):.2f})")
                        return
                    self.request_match_selection.emit(game_key, candidates)
                except Exception as e:
                    logger.debug(f"Error en ask_discord_match_for_new_game: {e}")
                finally:
                    self._ongoing_match_jobs.discard(game_key)

            threading.Thread(target=run, daemon=True).start()

        except Exception as e:
            logger.debug(f"Error asegurando discord match: {e}")

    # Slot to receive the selected match from UI
    def on_match_selected(self, game_key: str, match: dict):
        if match:
             self._apply_discord_match(game_key, match)
        else:
             logger.info(f"ℹ️ Usuario ignoró match Discord para '{game_key}'")

    def check_internet_connection(self) -> bool:
        import socket
        try:
            # Try to connect to a reliable public host (e.g. Cloudflare DNS at 1.1.1.1) on port 53
            socket.setdefaulttimeout(1.5)
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(("1.1.1.1", 53))
            s.close()
            return True
        except Exception:
            return False

    def check_presence(self):
        try:
            self.check_quests() # Check optional quests
            
            # Check if connection has returned when offline
            if not getattr(self, "is_online", True):
                self._offline_ticks = getattr(self, "_offline_ticks", 0) + 1
                if self._offline_ticks >= 3:
                    self._offline_ticks = 0
                    if self.check_internet_connection():
                        self.is_online = True
                        logger.info("🌐 Conexión a internet restaurada. Reanudando scraping de Steam.")
            
            game = self.find_active_game()
            self.update_presence(game)


        except Exception as e:
            if str(e) not in (
                "'NoneType' object has no attribute 'get'",
                "cannot access local variable 'title' where it is not associated with a value",
            ):
                logger.error(f"❌ Error inesperado en el loop principal: {e}")
            try:
                if self.rpc: self.rpc.clear()
            except Exception:
                pass
            logger.debug("🧹close_fake_executable desde check_presence exception handler")
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
                # Use AppleScript to get the window title of GeForce NOW.
                # We do a wildcard search matching all GeForce processes (like GeForceNOW, GeForce NOW, GeForceNOWStreamer, etc.)
                # to be 100% robust and catch the active streaming window.
                cmd = """
                tell application "System Events"
                    set geforceProcesses to every process whose name contains "GeForce"
                    repeat with proc in geforceProcesses
                        try
                            set windowNames to name of every window of proc
                            if count of windowNames > 0 then
                                set firstWindow to item 1 of windowNames
                                if firstWindow is not "" then
                                    return firstWindow
                                end if
                            end if
                        end try
                    end repeat
                end tell
                return ""
                """
                result = subprocess.run(["osascript", "-e", cmd], capture_output=True, text=True)
                if result.returncode == 0:
                    title = result.stdout.strip()
                
                # FALLBACK FOR MACOS: If AppleScript failed to fetch the title (e.g. because of accessibility or screen recording permissions),
                # we read the last game launched directly from the GeForce NOW logs if a GFN process is running!
                if not title:
                    is_gfn_running = False
                    for proc in psutil.process_iter(attrs=['name']):
                        proc_name = (proc.info.get('name') or "").lower()
                        if "geforce" in proc_name:
                            is_gfn_running = True
                            break
                    if is_gfn_running:
                        log_path = Path(os.path.expanduser('~/Library/Application Support/NVIDIA/GeForceNOW/console.log'))
                        if log_path.exists():
                            try:
                                log_content = log_path.read_text(encoding='utf-8', errors='ignore')
                                drs_names = re.findall(r'\"DRSAppName\":\s*\"([^\"]+)\"', log_content)
                                if drs_names:
                                    title = drs_names[-1].strip()
                                else:
                                    launches = re.findall(r'Launch game ([^\\[\\n]+)', log_content)
                                    if launches:
                                        title = launches[-1].strip()
                            except Exception as log_err:
                                logger.debug(f"Error leyendo logs para fallback en macOS: {log_err}")

            elif IS_LINUX:
                # Linux logic using xprop (assumes X11 for now)
                # We could also try /proc, but window title usually needs X11/Wayland tools
                try:
                    # Check if xprop is available
                    # We are looking for a window with property _NET_WM_NAME or WM_NAME
                    # and class name (WM_CLASS) related to GeForceNOW (if it exists)
                    # For now, let's try a generic approach if the user is running it via browser/electron
                    
                    # Alternative: use standard 'w' tool or similar if available, but xprop is standard-ish for X11
                    
                    # We will try to find a window with "GeForce NOW" in title
                    # cmd: xprop -root _NET_ACTIVE_WINDOW
                    # then get title
                    
                    # Simple approach: Check all windows (requires tools)
                    # Better: rely on process name first?
                    # GFN on linux is likely Chrome/Edge.
                    
                    # NOTE: Since GFN is web-based on Linux usually, detection might be tricky without a dedicated app.
                    # If this is for a dedicated Electron wrapper, we assume process name matches.
                    
                    pass 
                except Exception:
                    pass
                
                # Placeholder for Linux title detection
                # If running via Browser, title might be "GeForce NOW - Google Chrome"
                pass
            
            if not title:
                self.log_once("⚠️ GeForce NOW no está abierto (o sin ventana activa)")
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

            clean = re.sub(r'\s*(en|on|in|via)?\s*GeForce\s*NOW.*$', '', title, flags=re.IGNORECASE).strip()
            clean = re.sub(r'[®™]', '', clean).strip()
            
            last_clean = getattr(self, "_last_clean_title", None)
            if clean != last_clean:
                setattr(self, "_last_clean_title", clean)
            if not clean:
                return None

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
                            logger.info(f"✅ Steam AppID actualizado en JSON para: {game_name} -> {appid}")
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
                            logger.debug(f"no se pudo iniciar hilo de discord-match (update): {e}")

                    # Asegurar que el nombre está en el objeto devuelto
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
            logger.info(f"🆕 Juego agregado a config: {clean} (AppID: {appid})")
            self.games_map = games_config

            try:
                threading.Thread(
                    target=self._ensure_discord_match,
                    args=(clean,),
                    daemon=True
                ).start()
            except Exception as e:
                logger.debug(f"no se pudo iniciar hilo de discord-match: {e}")
            return new_game

        except Exception as e:
            if str(e) == "cannot access local variable 'title' where it is not associated with a value":
                self.log_once(f"⚠️ GeForce NOW está cerrado")
            else:
                logger.error(f"⚠️ Error detectando juego activo: {e}")

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
                    if name in ("geforcenow", "geforce now"):
                        return True
                else:
                    if "geforcenow" in name:
                        return True
        except Exception as e:
            logger.debug(f"Error comprobando procesos: {e}")
        return False
    
    def clear_forced_game(self):
        if self.forced_game:
            logger.info(f"🧹 Modo forzado desactivado: {self.forced_game.get('name')}")
            self.forced_game = None

    def update_presence(self, game_info: Optional[dict]):
        if getattr(self, "forced_game", None):
            game_info = self.forced_game
            current_time = time.time()
            if not hasattr(self, "_last_forced_log") or current_time - self._last_forced_log > 300:
                logger.info(f"🔧 Modo forzado activo: {self.forced_game.get('name')}")
                self._last_forced_log = current_time

        if (hasattr(self, "_force_stop_time") and 
            getattr(self, "_last_forced_game", None) and 
            game_info and 
            game_info.get("name") == self._last_forced_game.get("name")):
            
            current_time = time.time()
            if current_time - self._force_stop_time < 10:
                logger.debug(f"⏸️  Evitando reconexión automática a {game_info.get('name')} tras detener forzado")
                try:
                    if self.rpc: self.rpc.clear()
                except Exception:
                    pass
                self.last_game = None
                self.emit_presence_status()
                return

        # Resolve lobby status before checking game changes
        current_game = game_info or None
        if not current_game:
            show_lobby = True
            if self.config_manager:
                show_lobby = self.config_manager.get_setting("show_lobby_status", True)
            
            if self.is_geforce_running() and show_lobby:
                current_game = {
                    "name": "GeForce NOW",
                    "client_id": "1095416975028650046",
                    "image": "geforce",
                    "custom_details": self.texts.get("lobby_status", "En el menú principal"),
                }

        # Check if game has actually changed using the resolved game dicts
        game_changed = not self.is_same_game(self.last_game, current_game)
        
        status, group_size = None, None
        if current_game and current_game.get("steam_appid"):
            # Check online status before invoking scraper to handle offline state gracefully
            if getattr(self, "is_online", True):
                import requests
                try:
                    status, group_size = self.scraper.get_rich_presence()
                except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                    logger.warning(f"🔌 Conexión a internet perdida al consultar Steam. Entrando en modo offline: {e}")
                    self.is_online = False
                    self._offline_ticks = 0
                except Exception as e:
                    logger.debug(f"Error scraping rich presence: {e}")
            else:
                logger.debug("Scraping omitido: Modo offline activo.")
        
        if current_game and current_game.get("name") in self.games_map:
            defaults = self.games_map[current_game["name"]]
            merged = {**defaults, **current_game}
            # Protect custom presence keys from being overwritten by defaults
            for k in ("custom_details", "custom_state", "custom_party_size_current", "custom_party_size_max"):
                if k in defaults:
                    merged[k] = defaults[k]
            current_game = merged

        # Check if missing client_id and ensure match
        if current_game:
            if not current_game.get("client_id"):
                self._ensure_discord_match(current_game["name"])

        if game_changed:
            transition = (self.last_game.copy() if isinstance(self.last_game, dict) else self.last_game,
                          current_game.copy() if isinstance(current_game, dict) else current_game)
            last_transition = getattr(self, "_last_handled_transition", (None, None))
            
            if not self.is_same_game(last_transition[0], transition[0]) or not self.is_same_game(last_transition[1], transition[1]):
                self._last_handled_transition = transition
                logger.info(f"🔍 DEBUG: Game Changed detected.")
                logger.info(f"   OLD: {self.last_game}")
                logger.info(f"   NEW: {current_game}")
                
                logger.debug(f"🧹close_fake_executable desde update_presence (game_changed)")
                self.close_fake_executable()
                if current_game and current_game.get("executable_path"):
                    self.launch_fake_executable(current_game["executable_path"], current_game.get("name"))
                
                if current_game:
                    self.current_game_start_time = int(time.time())

        # If current_game is still None, GFN is not running or show_lobby_status is disabled
        if not current_game:
            if self.last_game is not None:
                try:
                    if self.rpc: self.rpc.clear()
                except Exception:
                    pass
                self.last_game = None
                self.current_game_start_time = None
            self.emit_presence_status()
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
                    self.log_once(f"🔁 Cambiado client_id a {client_id}")
                else:
                    self.log_once(f"🔁 Reconectado client_id {client_id}")

        # Determine Max Size settings first to decide how to format text
        max_size_setting = current_game.get("max_party_size")
        
        # Default behavior: Put the full presence status in details
        details = status
        state = None
        party_size_data = None

        if max_size_setting:
            try:
                max_size = int(max_size_setting)
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
        
        # If no real state, check custom
        if not has_real_state and custom_state is not None and len(str(custom_state).strip()) > 0:
            state = str(custom_state)
            
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
        show_lobby = True
        if self.config_manager:
            show_lobby = self.config_manager.get_setting("show_lobby_status", True)

        if rn in ["games", ""] or (rn == "geforce now" and not show_lobby):
            try:
                if self.rpc: self.rpc.clear()
            except:
                pass
            self.last_game = None
            self.emit_presence_status()
            return

        presence_data = {
            "details": details,
            "state": state,
            "large_image": current_game.get('image', 'steam'),
            "large_text": current_game.get('name'),
            "small_image": None,
            "start": self.current_game_start_time,
            "buttons": [
                {"label": self.texts.get("play_on_gfn", "Jugar en GeForce NOW"), "url": "https://play.geforcenow.com/mall/"},
                {"label": "GFN Rich Presence", "url": "https://github.com/KarmaDevz/GeForce-NOW-Rich-Presence"}
            ]
        }
        
        if party_size_data:
            presence_data["party_size"] = party_size_data

        try:
            if self.rpc and not getattr(self, "_is_connecting", False) and getattr(self, "_connected_client_id", None) == client_id:
                self.rpc.update(**{k: v for k, v in presence_data.items() if v})
        except Exception as e:
            msg = str(e).lower()
            logger.error(f"❌ Error actualizando Presence: {e}")
            if "pipe was closed" in msg or "socket.send()" in msg:
                try:
                    time.sleep(5) 
                    self._connect_rpc(client_id)
                    logger.info("🔁 Reconectado con Discord RPC tras error de socket")
                except Exception as e2:
                    logger.error(f"❌ Falló la reconexión a Discord RPC: {e2}")

        self.last_game = dict(current_game) if isinstance(current_game, dict) else current_game
        
        if (hasattr(self, "_force_stop_time") and 
            time.time() - self._force_stop_time >= 10):
            if hasattr(self, "_last_forced_game"):
                del self._last_forced_game
            if hasattr(self, "_force_stop_time"):
                del self._force_stop_time
        
        self.emit_presence_status()

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
    
        # Actualiza el juego forzado o el último juego
        if self.forced_game:
            self.forced_game.update(data)
        if self.last_game:
            self.last_game.update(data)
            
        self.update_presence(game) # Pasa el objeto
        return True

    def emit_presence_status(self):
        forced = getattr(self, "forced_game", None)
        active = self.last_game
        
        if forced:
            state = "forced"
            gname = forced.get('name', 'Unknown')
            text = self.texts.get("status_forced", "Forced: {game}").replace("{game}", gname)
        elif active and self.rpc and getattr(self, "_connected_client_id", None):
            state = "active"
            gname = active.get('name', 'Unknown')
            if gname == "GeForce NOW":
                text = self.texts.get("status_searching", "Buscando juego...")
            else:
                text = self.texts.get("status_active", "Active: {game}").replace("{game}", gname)
        else:
            state = "disconnected"
            text = self.texts.get("status_disconnected", "Disconnected")
            
        discord_connected = self.rpc is not None and getattr(self, "_connected_client_id", None) is not None
        gfn_running = self.is_geforce_running()
        
        self.presence_updated.emit(state, text, discord_connected, gfn_running)

    def close(self):
        if self.rpc:
            try:
                self.rpc.clear()
                self.rpc.close()
                time.sleep(0.1) 
                self._connected_client_id = None
                logger.debug("🧹close_fake_executable desde close")
                self.close_fake_executable()
                logger.info("🔴 Discord RPC cerrado correctamente.")
            except Exception:
                pass
        self.last_game = None
        self.emit_presence_status()
