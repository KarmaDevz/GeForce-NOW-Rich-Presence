import os
import time
import logging
import requests
import psutil
from pathlib import Path
from typing import Optional, Callable, Dict

try:
    import browser_cookie3
except ImportError:
    browser_cookie3 = None

from selenium import webdriver
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.edge.options import Options
from selenium.common.exceptions import WebDriverException

from src.core.utils import save_cookie_to_env, DRIVER_PATH, ensure_driver_executable, ENV_PATH, IS_WINDOWS, IS_MACOS, IS_LINUX

logger = logging.getLogger('geforce_presence')

class CookieManager:
    def __init__(self, texts: Dict, env_cookie: Optional[str] = None, test_url: str = ""):
        self.texts = texts
        self.env_cookie = env_cookie
        self.test_url = test_url
        self.driver_path = str(ensure_driver_executable(DRIVER_PATH))

    def validate_cookie(self, cookie_value: str) -> bool:
        try:
            s = requests.Session()
            s.cookies.set('steamLoginSecure', cookie_value, domain='steamcommunity.com')
            r = s.get(self.test_url, timeout=10)
            if r.status_code == 200 and "Sign In" not in r.text and "login" not in r.url.lower():
                return True
        except Exception as e:
            logger.debug(f"Error validating cookie: {e}")
        return False

    def get_cookie_from_edge_profile(self) -> Optional[str]:
        if not browser_cookie3:
            logger.warning("browser_cookie3 not installed.")
            return None
            
        browsers_to_try = [
            ('Firefox', browser_cookie3.firefox),
            ('Chrome', browser_cookie3.chrome),
            ('Brave', browser_cookie3.brave),
            ('Chromium', browser_cookie3.chromium),
            ('Edge', browser_cookie3.edge),
        ]
        
        for name, get_cookies in browsers_to_try:
            try:
                logger.info(f"🧩 Attempting to read Steam cookie from {name} (browser_cookie3)...")
                cj = get_cookies(domain_name='steamcommunity.com')
                for cookie in cj:
                    if cookie.name == 'steamLoginSecure':
                        val = cookie.value
                        logger.info(f"✅ Automatic cookie obtained from {name} (browser_cookie3).")
                        save_cookie_to_env(val, ENV_PATH)
                        return val
            except Exception as e:
                logger.debug(f"browser_cookie3 ({name}) failed: {e}")
                
        logger.info("⚠️ No steamLoginSecure cookie found in any accessible browser profile.")
        return None
    
    def close_edge_processes(self):
        """Closes all Microsoft Edge processes."""
        closed = 0
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if proc.info['name'] and "msedge.exe" in proc.info['name'].lower():
                    proc.terminate()
                    closed += 1
            except Exception:
                continue
        if closed:
            logger.info(f"🔒 {closed} Edge processes terminated.")
        else:
            logger.debug("No Edge processes running.")

    def get_cookie_with_selenium(self, 
                                 headless: bool = False, 
                                 profile_dir: str = "Default", 
                                 confirm_callback: Optional[Callable[[str, str], bool]] = None,
                                 _is_retry: bool = False) -> Optional[str]:
        try:
            # Check if Edge is running
            edge_running = any(
                (p.info['name'] and "msedge.exe" in p.info['name'].lower())
                for p in psutil.process_iter(['name'])
            )

            if edge_running:
                if confirm_callback:
                    res = confirm_callback(
                        self.texts.get("edge_open", "Microsoft Edge está abierto"), 
                        self.texts.get('edge_open_confirm', 'Edge needs to be closed to proceed. Close it?')
                    )
                    if not res:
                        logger.info("⏭️ User cancelled cookie extraction because Edge was open.")
                        return None
                else:
                    logger.info("Edge is running and no callback provided to confirm close.")
                    return None

                self.close_edge_processes()
                time.sleep(2)

            logger.info("🧩 Obtaining Steam cookie with Selenium (Edge)...")
            
            user_data_dir = ""
            if IS_WINDOWS:
                localapp = os.getenv("LOCALAPPDATA", "")
                user_data_dir = str(Path(localapp) / "Microsoft" / "Edge" / "User Data")
            elif IS_MACOS:
                user_data_dir = str(Path.home() / "Library" / "Application Support" / "Microsoft Edge")
            elif IS_LINUX:
                user_data_dir = str(Path.home() / ".config" / "microsoft-edge")

            if not user_data_dir or not Path(user_data_dir).exists():
                logger.error(f"❌ Edge profiles folder not found at: {user_data_dir}")
                # Try to proceed anyway? Selenium might create a temp one if not found, but we want the specific profile.
                if not Path(user_data_dir).exists():
                     pass # Logged above, but let's see if we can continue or return
                # return None # Returning None might be safer if we strictly need the user's cookies.

            service = EdgeService(executable_path=self.driver_path)
            options = Options()
            options.add_argument(f"--user-data-dir={user_data_dir}")
            options.add_argument(f"--profile-directory={profile_dir}")
            
            # Anti-crash flags
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            
            if headless:
                options.add_argument("--headless=new")

            driver = webdriver.Edge(service=service, options=options)
            try:
                driver.get("https://steamcommunity.com")
                cookies = driver.get_cookies()
                for c in cookies:
                    if c.get('name') == 'steamLoginSecure':
                        val = c.get('value')
                        save_cookie_to_env(val, ENV_PATH)
                        logger.debug(f"Partially obtained cookie: {val[:20]}... (length: {len(val)})")
                        logger.info("✅ Cookie obtained with Selenium.")
                        return val
                logger.warning("⚠️ 'steamLoginSecure' not found in Steam session.")
            finally:
                driver.quit()
                
        except WebDriverException as e:
            msg = getattr(e, "msg", str(e))
            logger.error(f"❌ Selenium WebDriver error: {msg}")

            # Detect exactly the version error
            if "only supports Microsoft Edge version" in msg or "Unable to obtain driver for MicrosoftEdge" in msg:
                if _is_retry:
                    logger.error("❌ Already tried updating WebDriver and failed. Aborting to prevent infinite loop.")
                    return None

                logger.warning("🔄 Edge WebDriver outdated. Attempting to update...")

                try:
                    from src.core.edge_updater import EdgeDriverUpdater
                    driver_updater = EdgeDriverUpdater(parent_widget=None)
                    driver_updater.update()
                    
                    # Refresh the driver path copied in temp
                    self.driver_path = str(ensure_driver_executable(DRIVER_PATH))
                    logger.info("🆗 WebDriver updated successfully. Retrying Selenium...")

                    # Retry only ONCE
                    return self.get_cookie_with_selenium(
                        headless=headless,
                        profile_dir=profile_dir,
                        confirm_callback=confirm_callback,
                        _is_retry=True
                    )

                except Exception as update_error:
                    logger.error(f"❌ Error updating Edge WebDriver: {update_error}")

            else:
                logger.error("⚠️ Selenium error not related to outdated driver.")
        except Exception as e:
            logger.error(f"⚠️ Unexpected error obtaining cookie with Selenium: {e}")
            return None

    def get_steam_cookie(self, confirm_callback: Optional[Callable[[str, str], bool]] = None) -> Optional[str]:
        if self.env_cookie:
            logger.info("🧩 Validating cookie from .env...")
            if self.validate_cookie(self.env_cookie):
                logger.info("✅ Cookie from .env is valid.")
                return self.env_cookie
            else:
                logger.warning("⚠️ Cookie from .env is expired or invalid.")

        c = self.get_cookie_from_edge_profile()
        if c and self.validate_cookie(c):
            return c

        # If we are here, we need to ask user permission to use Selenium if not headless/silent
        if confirm_callback:
             if not confirm_callback("Cookie", self.texts.get('ask_cookie', 'Obtain cookie via Edge?')):
                 return None

        c2 = self.get_cookie_with_selenium(headless=False, confirm_callback=confirm_callback)
        if c2 and self.validate_cookie(c2):
            return c2

        logger.error("❌ Could not obtain Steam cookie automatically.")
        return None

    def ask_and_obtain_cookie(self, confirm_callback: Callable[[str, str], bool]) -> Optional[str]:
        """Interactive version"""
        try:
            should = confirm_callback("Cookie", 
                                self.texts.get('ask_cookie', 'The program will try to obtain your Steam cookie using Microsoft Edge. Make sure you are logged in to Steam in Edge.\n\nDo you want to continue?'))

            if not should:
                logger.info("Steam cookie not obtained interactively.")
                return None

            c2 = self.get_cookie_with_selenium(headless=False, confirm_callback=confirm_callback)
            if c2 and self.validate_cookie(c2):
                return c2
            
            c = self.get_cookie_from_edge_profile()
            if c and self.validate_cookie(c):
                return c

            logger.warning("Could not obtain cookie automatically after user request.")
            return None
            
        except Exception as e:
            logger.error(f"Error in ask_and_obtain_cookie: {e}")
            return None
