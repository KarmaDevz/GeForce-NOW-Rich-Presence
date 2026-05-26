import sys
import os
import logging
import signal
from logging.handlers import RotatingFileHandler
from pathlib import Path
from dotenv import load_dotenv

from PyQt5.QtWidgets import QApplication

from src.core.utils import (
    BASE_DIR, CONFIG_DIR, LOGS_DIR, LANG_DIR, ASSETS_DIR, LOG_FILE, ENV_PATH,
    get_lang_from_registry, load_locale, ensure_env_file, acquire_lock, release_lock,
    set_autostart_windows, IS_WINDOWS, IS_LINUX, IS_MACOS
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

def main():
    import argparse
    import time
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--delay", type=int, default=0, help="Delay startup by N seconds")
    args, unknown = parser.parse_known_args()
    
    if args.delay > 0:
        logger.info(f"Waiting {args.delay} seconds before starting...")
        time.sleep(args.delay)

    # 1. Ensure .env and load it
    actual_env_path = ensure_env_file(ENV_PATH)
    try:
        load_dotenv(actual_env_path)
        logger.debug(".env loaded")
    except Exception:
        logger.debug("python-dotenv not available or .env not found")

    # 2. Acquire Lock
    if not acquire_lock():
        logger.warning("Another instance is already running. Exiting.")
        sys.exit(0)

    # 3. Load Locale
    try:
        lang = get_lang_from_registry()
        texts = load_locale(lang)
    except Exception:
        lang = os.getenv('GEFORCE_LANG', 'en')
        texts = load_locale(lang)

    # 4. Initialize PyQt Application
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False) # Important for tray apps

    # 5. Check for Updates
    updater = Updater()
    updater.check_for_updates(silent=True)

    # 6. Initialize Managers First (moved up so we can read settings)
    config_manager = ConfigManager(CONFIG_DIR / "config_path.txt")

    if IS_WINDOWS and config_manager.get_setting("start_with_windows", False):
        try:
            import winshell
            app_name = "GeForceNOWRichPresence"
            shortcut_path = os.path.join(winshell.startup(), f"{app_name}.lnk")
            if not os.path.exists(shortcut_path):
                logger.info("Creating missing Windows startup shortcut...")
                set_autostart_windows(True)
        except ImportError:
            logger.debug("winshell not available to verify startup shortcut.")
        except Exception as e:
            logger.error(f"Error checking Windows startup shortcut: {e}")

    # 5.1 Launch Apps
    if config_manager.get_setting("start_discord_on_launch", False):
        AppLauncher.launch_discord()
    
    if config_manager.get_setting("start_gfn_on_launch", False):
        AppLauncher.launch_geforce_now()

    # 5.2 Update Edge Driver
    #MOVE TO TRAY ICON
    
    test_rich_url = os.getenv("TEST_RICH_URL", "").strip()
    client_id = os.getenv("CLIENT_ID", "").strip() or "1095416975028650046"
    steam_cookie_env = os.getenv("STEAM_COOKIE", "").strip() or None
    update_interval = int(os.getenv("UPDATE_INTERVAL", "10"))

    cookie_manager = CookieManager(texts, steam_cookie_env, test_rich_url)
    
    presence_manager = PresenceManager(
        client_id=client_id,
        games_map=config_manager.get_game_mapping(),
        cookie_manager=cookie_manager,
        test_rich_url=test_rich_url,
        texts=texts,
        update_interval=update_interval
    )

    # 6.1 Optional Cookie Fetch
    if config_manager.get_setting("get_cookie_on_launch", True) or not steam_cookie_env:
        logger.info("Attempting to obtain Steam cookie on startup...")
        cookie = cookie_manager.get_steam_cookie(confirm_callback=None)
        if cookie:
            presence_manager.update_cookie(cookie)

    # Cleanup residues from previous sessions
    logger.info(" 🧹 Cleaning up residues from previous sessions...")
    presence_manager.close_fake_executable()

    # 7. Initialize UI
    tray_icon = SystemTrayIcon(presence_manager, texts, config_manager)
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
