import sys
import os
import logging
import signal
from logging.handlers import RotatingFileHandler
from pathlib import Path
from dotenv import load_dotenv

from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QFontDatabase

from src.core.utils import (
    BASE_DIR, CONFIG_DIR, LOGS_DIR, LANG_DIR, ASSETS_DIR, LOG_FILE, ENV_PATH,
    get_lang_from_registry, load_locale, ensure_env_file, acquire_lock, release_lock,
    set_autostart_windows, IS_WINDOWS
)
from src.core.config_manager import ConfigManager
from src.core.cookie_manager import CookieManager
from src.core.presence_manager import PresenceManager
from src.ui.tray_icon import SystemTrayIcon
from src.core.updater import Updater
from src.core.app_launcher import AppLauncher

# Setup Logging
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)
ASSETS_DIR.mkdir(parents=True, exist_ok=True)
LANG_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger('geforce_presence')
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')

fh = RotatingFileHandler(str(LOG_FILE), maxBytes=5 * 1024 * 1024, backupCount=3, encoding='utf-8')
fh.setLevel(logging.DEBUG)
fh.setFormatter(formatter)
logger.addHandler(fh)

sh = logging.StreamHandler()
sh.setLevel(logging.DEBUG)
sh.setFormatter(formatter)
logger.addHandler(sh)

logger.debug(f"Base directory: {BASE_DIR}")
logger.debug(f"Config directory: {CONFIG_DIR}")
logger.debug(f"Logs directory: {LOGS_DIR}")

import traceback
import threading
from PyQt5.QtCore import QObject, pyqtSignal

class ExceptionSignaler(QObject):
    exception_caught = pyqtSignal(str)

exception_signaler = None
main_presence_manager = None

def show_crash_dialog_slot(tb_text):
    try:
        from src.ui.dialogs import CrashReporterDialog
        from src.core.utils import get_lang_from_registry, load_locale
        try:
            lang = get_lang_from_registry()
            texts = load_locale(lang)
        except Exception:
            texts = {}
        
        dlg = CrashReporterDialog(tb_text, texts)
        dlg.exec_()
    except Exception as e:
        logger.error(f"Error displaying crash reporter dialog: {e}")
        traceback.print_exc()
    finally:
        logger.info("Performing clean shutdown after unhandled crash...")
        
        # Cleanup presence_manager if initialized (Important for closing the application and the fake games)
        global main_presence_manager
        if main_presence_manager:
            try:
                main_presence_manager.stop_monitoring()
                main_presence_manager.close()
            except Exception as e:
                logger.error(f"Error stopping presence manager during shutdown: {e}")
                
        # Release single instance lock (this is for running just one instance)
        try:
            from src.core.utils import release_lock
            release_lock()
        except Exception as e:
            logger.error(f"Error creando lock: {e}")
            pass
            
        try:
            QApplication.quit()
        except Exception as e:
            logger.error(f"Error borrando aplicación: {e}")
            pass
            
        os._exit(1)

def global_exception_handler(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    # Log with CRITICAL level and details (this help to catch any main thread exceptions)
    logger.critical("Uncaught main thread exception:", exc_info=(exc_type, exc_value, exc_traceback))
    
    try:
        tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
        tb_text = "".join(tb_lines)
        
        global exception_signaler
        if exception_signaler is not None:
            # If signaler is active, emit to main thread thread-safely (when app crashes, it's important to show the dialog in the main thread)
            exception_signaler.exception_caught.emit(tb_text)
        else:
            # Fallback if exception occurs before signaler is initialized (when app crashes before the main thread is initialized)
            print("Early crash (no UI exception signaler):", tb_text, file=sys.stderr)
            os._exit(1)
    except Exception:
        traceback.print_exc()
        os._exit(1)

def global_thread_exception_handler(args):
    # Log with CRITICAL level
    logger.critical("Uncaught background thread exception:", exc_info=(args.exc_type, args.exc_value, args.exc_traceback))
    
    try:
        tb_lines = traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)
        tb_text = "".join(tb_lines)
        
        global exception_signaler
        if exception_signaler is not None:
            exception_signaler.exception_caught.emit(tb_text)
        else:
            print("Early thread crash (no UI exception signaler):", tb_text, file=sys.stderr)
            os._exit(1)
    except Exception:
        traceback.print_exc()
        os._exit(1)

sys.excepthook = global_exception_handler
threading.excepthook = global_thread_exception_handler


def main():
    import argparse
    import time
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--delay", type=int, default=0, help="Delay startup by N seconds")
    parser.add_argument("--logs", action="store_true", help="Abrir directamente el visor de logs sin iniciar la presencia")
    args, unknown = parser.parse_known_args()
    
    # 0. Standalone Log Viewer Mode
    if args.logs:
        try:
            lang = get_lang_from_registry()
            texts = load_locale(lang)
        except Exception:
            lang = os.getenv('GEFORCE_LANG', 'en')
            texts = load_locale(lang)

        app = QApplication(sys.argv)
        for ext in ["ttf", "otf"]:
            p = ASSETS_DIR / f"font.{ext}"
            if p.exists():
                QFontDatabase.addApplicationFont(str(p))
                break

        from src.ui.dialogs import GamingLogViewerDialog
        dlg = GamingLogViewerDialog(texts)
        dlg.exec_()
        sys.exit(0)
    
    if args.delay > 0:
        logger.info(f"Esperando {args.delay} segundos antes de iniciar...")
        time.sleep(args.delay)

    # 1. Ensure .env and load it
    actual_env_path = ensure_env_file(ENV_PATH)
    try:
        load_dotenv(actual_env_path)
        logger.debug(".env cargado")
    except Exception:
        logger.debug("python-dotenv no disponible o .env no encontrado")

    # 2. Acquire Lock
    if not acquire_lock():
        logger.warning("Otra instancia ya está corriendo. Saliendo.")
        sys.exit(0)

    # 3. Load Locale
    try:
        lang = get_lang_from_registry()
        texts = load_locale(lang)
    except Exception:
        lang = os.getenv('GEFORCE_LANG', 'en')
        texts = load_locale(lang)

    # Setup Windows JumpList
    if IS_WINDOWS:
        try:
            from src.core.jumplist import setup_jumplist
            setup_jumplist(texts)
        except Exception as e:
            logger.debug(f"No se pudo registrar JumpList: {e}")

    # 4. Initialize PyQt Application
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False) # Important for tray apps

    # Load custom font (ttf or otf)
    font_path = None
    for ext in ["ttf", "otf"]:
        p = ASSETS_DIR / f"font.{ext}"
        if p.exists():
            font_path = str(p)
            break

    if font_path:
        font_id = QFontDatabase.addApplicationFont(font_path)
        if font_id != -1:
            families = QFontDatabase.applicationFontFamilies(font_id)
            logger.info(f"Loaded custom font families: {families}")
        else:
            logger.error(f"Failed to load custom font from {font_path}")
    else:
        logger.warning("Custom font file (font.ttf or font.otf) not found in assets")

    global exception_signaler
    exception_signaler = ExceptionSignaler()
    exception_signaler.exception_caught.connect(show_crash_dialog_slot)

    # 5. Initialize Managers First
    config_manager = ConfigManager(CONFIG_DIR / "config_path.txt")

    # 5.1 Check for Updates
    updater = Updater(config_manager=config_manager)
    updater.check_for_updates(silent=True)

    if IS_WINDOWS and config_manager.get_setting("start_with_windows", False):
        try:
            # pyrefly: ignore [missing-import]
            import winshell
            app_name = "GeForceNOWRichPresence"
            shortcut_path = os.path.join(winshell.startup(), f"{app_name}.lnk")
            if not os.path.exists(shortcut_path):
                logger.info("Creando acceso directo de inicio de Windows faltante...")
                set_autostart_windows(True)
        except ImportError:
            logger.debug("winshell no disponible para comprobar acceso directo.")
        except Exception as e:
            logger.error(f"Error comprobando acceso directo de inicio de Windows: {e}")

    # 5.1 Launch Apps
    if IS_WINDOWS and config_manager.get_setting("start_discord_on_launch", False):
        AppLauncher.launch_discord()
    
    if IS_WINDOWS and config_manager.get_setting("start_gfn_on_launch", False):
        AppLauncher.launch_geforce_now()

    # 5.2 Update Edge Driver
    #MOVE TO TRAY ICON
    
    test_rich_url = os.getenv("TEST_RICH_URL", "").strip()
    client_id = os.getenv("CLIENT_ID", "").strip() or "1095416975028650046"
    steam_cookie_env = os.getenv("STEAM_COOKIE", "").strip() or None
    update_interval = int(os.getenv("UPDATE_INTERVAL", "10"))

    cookie_manager = CookieManager(texts, steam_cookie_env, test_rich_url, config_manager=config_manager)
    
    presence_manager = PresenceManager(
        client_id=client_id,
        games_map=config_manager.get_game_mapping(),
        cookie_manager=cookie_manager,
        test_rich_url=test_rich_url,
        texts=texts,
        config_manager=config_manager,
        update_interval=update_interval
    )

    global main_presence_manager
    main_presence_manager = presence_manager

    # 6.1 Optional Cookie Fetch
    if config_manager.get_setting("get_cookie_on_launch", True):
        logger.info("Intentando obtener cookie de Steam al inicio (según configuración)...")
        cookie = cookie_manager.get_steam_cookie(confirm_callback=None)
        if cookie:
            presence_manager.update_cookie(cookie)

    # Cleanup residues from previous sessions
    logger.info(" 🧹 Limpiando residuos de sesiones anteriores...")
    presence_manager.close_fake_executable()

    # 7. Initialize UI
    tray_icon = SystemTrayIcon(presence_manager, texts, config_manager, updater=updater)
    tray_icon.show()

    # 8. Start Monitoring
    presence_manager.start_monitoring()

    # 9. Handle Signals
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    # 10. Run Loop
    exit_code = app.exec_()
    
    # Cleanup
    presence_manager.stop_monitoring()
    release_lock()
    
    # Clean shutdown for asyncio/Windows
    import gc
    import time
    gc.collect()
    time.sleep(0.2)
    
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
