import sys
import os
import json
import logging
import shutil
import stat
import tempfile
import psutil
import atexit
import subprocess
from pathlib import Path
from typing import Optional, Dict
import hashlib
from dotenv import set_key

# Platform detection
IS_WINDOWS = sys.platform == "win32"
IS_MACOS = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")

if IS_WINDOWS:
    import winreg

logger = logging.getLogger('geforce_presence')

def resource_path(*parts):
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    else:
        # Assuming src/core/utils.py, so we need to go up two levels to get to root
        base = Path(__file__).resolve().parent.parent.parent
    return base.joinpath(*parts)

# Define common paths
BASE_DIR = resource_path("")      
CONFIG_DIR = resource_path("config")
LOGS_DIR = resource_path("logs")
LANG_DIR = resource_path("lang")
ASSETS_DIR = resource_path("assets")
# Driver path depends on OS
if IS_WINDOWS:
    DRIVER_PATH = resource_path("tools", "msedgedriver.exe")
elif IS_MACOS:
    DRIVER_PATH = resource_path("tools", "msedgedriver_mac") 
else:
    DRIVER_PATH = resource_path("tools", "msedgedriver_linux")

LOG_FILE = LOGS_DIR / "geforce_presence.log"
ENV_PATH = resource_path(".env")
DISCORD_CACHE_PATH = CONFIG_DIR / "discord_apps_cache.json"
DISCORD_DETECTABLE_URL = "https://discord.com/api/v9/applications/detectable"
DISCORD_CACHE_TTL = 60 * 60 * 24  # 1 day
DISCORD_AUTO_APPLY_THRESHOLD = 0.85
DISCORD_ASK_TIMEOUT = 10
LOCK_FILE = Path(tempfile.gettempdir()) / "geforce_presence.lock"

def get_lang_from_registry(default="en"):
    if IS_WINDOWS:
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\GeForcePresence")
            lang, _ = winreg.QueryValueEx(key, "lang")
            winreg.CloseKey(key)
            return _normalize_lang(lang, default)
        except Exception:
            return default
    elif IS_MACOS:
        try:
            # Try reading from macOS defaults
            # defaults read com.nvidia.geforcenow lang
            # Note: This assumes the app stores it there, or we check system lang
            result = subprocess.run(
                ["defaults", "read", "com.nvidia.geforcenow", "lang"],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                return _normalize_lang(result.stdout.strip(), default)
        except Exception:
            pass
        
        # Fallback to system locale
        lang = os.getenv("LANG", default)
        return _normalize_lang(lang, default)
    
    elif IS_LINUX:
        lang = os.getenv("LANG", default)
        if "." in lang:
            lang = lang.split(".")[0]
        return _normalize_lang(lang, default)

    return default

def _normalize_lang(lang_str: str, default: str) -> str:
    lang_str = lang_str.lower()
    if "spanish" in lang_str or "es" in lang_str:
        return "es"
    elif "english" in lang_str or "en" in lang_str:
        return "en"
    return default

def set_autostart_windows(enable: bool):
        
    try:
        import winshell
    except ImportError:
        logger.error("winshell no está instalado o falló su importación.")
        return

    app_name = "GeForceNOWRichPresence"
    startup_folder = winshell.startup()
    shortcut_path = os.path.join(startup_folder, f"{app_name}.lnk")
    
    # El ejecutable real si está empaquetado; si no, el sys.executable y el script
    if getattr(sys, 'frozen', False):
        target_path = sys.executable
        arguments = "--delay 60"
    else:
        # Modo desarrollo
        target_path = sys.executable
        script_path = str(Path(__file__).resolve().parent.parent.parent / "src" / "GeForceNOWRichPresence.py")
        arguments = f'"{script_path}" --delay 60'
        
    try:
        # Limpiar registro y schtasks antiguo por si acaso
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE | winreg.KEY_READ)
            winreg.DeleteValue(key, app_name)
            winreg.CloseKey(key)
        except Exception:
            pass
            
        try:
            subprocess.run(["schtasks", "/delete", "/tn", app_name, "/f"], creationflags=0x08000000)
        except Exception:
            pass

        if enable:
            # Crear el acceso directo en Inicio
            with winshell.shortcut(shortcut_path) as shortcut:
                shortcut.path = target_path
                shortcut.arguments = arguments
                shortcut.description = "Start GeForce NOW Rich Presence"
            logger.info("✅ Acceso directo creado en shell:startup para iniciar con Windows (retraso 60s).")
        else:
            # Eliminar el acceso directo
            if os.path.exists(shortcut_path):
                os.remove(shortcut_path)
            logger.info("✅ Acceso directo eliminado de shell:startup.")
    except Exception as e:
        logger.error(f"Error modificando inicio de Windows (winshell): {e}")

def set_autostart_linux(enable: bool):
    autostart_dir = Path.home() / ".config" / "autostart"
    autostart_dir.mkdir(parents=True, exist_ok=True)
    desktop_file = autostart_dir / "geforce_presence.desktop"

    if enable:
        content = f"""[Desktop Entry]
Type=Application
Exec=python3 {os.path.abspath(__file__)}
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
Name=GeForce NOW Presence
Comment=Launch GeForce NOW Presence at login
Terminal=false
"""
        desktop_file.write_text(content)
    else:
        if desktop_file.exists():
            desktop_file.unlink()

def load_locale(lang: str = "en") -> dict:
    path = LANG_DIR / f"{lang}.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    try:
        return json.loads((LANG_DIR / "en.json").read_text(encoding="utf-8"))
    except Exception:
        return {}

def ensure_env_file(path: Path):
    default_env_content = """CLIENT_ID = '1095416975028650046'
UPDATE_INTERVAL = 10
CONFIG_PATH_FILE = ''
TEST_RICH_URL = 'https://steamcommunity.com/dev/testrichpresence'
STEAM_COOKIE=''
"""
    try:
        if not path.exists():
            path.write_text(default_env_content, encoding="utf-8")
            logger.info(f"✅ .env creado en: {path}")
    except PermissionError:
        if IS_WINDOWS:
            appdata = Path(os.getenv("APPDATA", Path.home() / "AppData" / "Roaming"))
        elif IS_MACOS:
            appdata = Path.home() / "Library" / "Application Support"
        else:
            appdata = Path.home() / ".config"
            
        appdir = appdata / "geforce_presence"
        appdir.mkdir(parents=True, exist_ok=True)
        alt = appdir / ".env"
        if not alt.exists():
            alt.write_text(default_env_content, encoding="utf-8")
            logger.info(f"⚠️ No se pudo crear .env junto al exe; creado en: {alt}")
        return alt
    return path

def ensure_driver_executable(src_path: Path) -> str:
    try:
        if not src_path.exists():
            logger.warning(f"Driver no encontrado en recursos: {src_path}")
            return str(src_path) 
        tmpdir = Path(tempfile.gettempdir()) / "geforce_driver"
        tmpdir.mkdir(parents=True, exist_ok=True)
        dest = tmpdir / src_path.name
        shutil.copy2(str(src_path), str(dest))
        try:
            dest.chmod(dest.stat().st_mode | stat.S_IEXEC)
        except Exception:
            pass
        return str(dest)
    except Exception as e:
        logger.error(f"Error preparando driver: {e}")
        return str(src_path)

def acquire_lock() -> bool:
    if LOCK_FILE.exists():
        try:
            pid = int(LOCK_FILE.read_text().strip())

            if psutil.pid_exists(pid):
                logger.warning(f"⚠️ Ya existe otra instancia (PID {pid}). Reiniciando...")
                try:
                    # Cierra la instancia anterior (si es posible)
                    p = psutil.Process(pid)
                    p.terminate()
                    p.wait(5)
                    logger.info("✅ Instancia anterior finalizada correctamente.")
                except Exception as e:
                    logger.error(f"No se pudo cerrar la instancia anterior: {e}")
                
                # We don't restart here, we just return False or let the caller handle it.
                # The original code restarted the process.
                # For now, let's just return False if we can't kill it, or True if we killed it.
                # Actually, the original code tries to restart itself.
                # "os.execv(sys.executable, [sys.executable] + sys.argv)"
                # We should probably let the main function handle this logic or keep it here.
                # Let's keep the kill logic but maybe not the restart logic inside utils?
                # If we kill the other instance, we can proceed.
                
                # Wait a bit
                import time
                time.sleep(2)
                
                # If we are here, we killed the other process (or tried to). 
                # We can try to proceed.
            else:
                LOCK_FILE.unlink()
                logger.debug("Lock huérfano eliminado.")
        except Exception:
            try:
                LOCK_FILE.unlink()
            except Exception:
                pass

    LOCK_FILE.write_text(str(os.getpid()))
    atexit.register(release_lock)
    return True

def release_lock():
    try:
        if LOCK_FILE.exists():
            LOCK_FILE.unlink()
    except Exception:
        pass

def safe_json_load(path: Path) -> Optional[Dict]:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error cargando JSON {path}: {e}")
        return None

def save_cookie_to_env(cookie_value: str, env_path: Path):
    try:
        if env_path.exists():
            set_key(str(env_path), "STEAM_COOKIE", cookie_value)
            logger.info("💾 Cookie guardada en .env correctamente.")
        else:
            logger.warning("⚠️ No se encontró el archivo .env para guardar la cookie.")
    except Exception as e:
        logger.error(f"❌ Error guardando cookie en .env: {e}")

def save_json(obj, path: Path):
    try:
        with path.open("w", encoding="utf-8") as f:
            json.dump(obj, f, indent=4, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error guardando JSON {path}: {e}")

def calculate_file_hash(path: Path, algorithm: str = "sha256") -> Optional[str]:
    try:
        hash_func = getattr(hashlib, algorithm)()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_func.update(chunk)
        return hash_func.hexdigest()
    except Exception as e:
        logger.error(f"Error calculando hash de {path}: {e}")
        return None
