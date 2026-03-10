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

from src.core.utils import (
    save_cookie_to_env,
    DRIVER_PATH,
    ensure_driver_executable,
    ENV_PATH,
    IS_WINDOWS,
    IS_MACOS,
    IS_LINUX
)

logger = logging.getLogger("geforce_presence")


class CookieManager:
    def __init__(self, texts: Dict, env_cookie: Optional[str] = None, test_url: str = ""):
        self.texts = texts
        self.env_cookie = env_cookie
        self.test_url = test_url
        self.driver_path = str(ensure_driver_executable(DRIVER_PATH))

    def validar_cookie(self, cookie_value: str) -> bool:
        try:
            s = requests.Session()
            s.cookies.set("steamLoginSecure", cookie_value, domain="steamcommunity.com")
            r = s.get(self.test_url, timeout=10)

            if r.status_code == 200 and "Sign In" not in r.text and "login" not in r.url.lower():
                return True

        except Exception as e:
            logger.debug(f"Error validando cookie: {e}")

        return False

    def get_cookie_from_browser(self) -> Optional[str]:

        if not browser_cookie3:
            logger.warning("browser_cookie3 no instalado.")
            return None

        browsers = []

        if IS_WINDOWS or IS_LINUX:
            browsers = [
                ("Edge", browser_cookie3.edge),
                ("Chrome", browser_cookie3.chrome),
                ("Chromium", browser_cookie3.chromium),
                ("Firefox", browser_cookie3.firefox),
            ]

        elif IS_MACOS:
            browsers = [
                ("Chrome", browser_cookie3.chrome),
                ("Edge", browser_cookie3.edge),
                ("Firefox", browser_cookie3.firefox),
            ]

        for name, loader in browsers:
            try:
                logger.info(f"🧩 Buscando cookie en {name}...")

                cj = loader(domain_name="steamcommunity.com")

                for cookie in cj:
                    if cookie.name == "steamLoginSecure":

                        logger.info(f"✅ Cookie encontrada en {name}.")
                        logger.debug(f"Cookie parcial: {cookie.value[:20]}...")

                        return cookie.value

            except Exception as e:
                logger.debug(f"{name} cookie read failed: {e}")

        logger.warning("⚠️ No se encontró cookie steamLoginSecure en ningún navegador.")
        return None

    def close_edge_processes(self):

        closed = 0

        for proc in psutil.process_iter(["pid", "name"]):
            try:
                if proc.info["name"] and "msedge" in proc.info["name"].lower():
                    proc.terminate()
                    closed += 1
            except Exception:
                continue

        if closed:
            logger.info(f"🔒 {closed} procesos de Edge terminados.")

    def get_cookie_with_selenium(
        self,
        headless: bool = False,
        profile_dir: str = "Default",
        confirm_callback: Optional[Callable[[str, str], bool]] = None,
        _is_retry: bool = False
    ) -> Optional[str]:

        try:

            edge_running = any(
                (p.info["name"] and "msedge" in p.info["name"].lower())
                for p in psutil.process_iter(["name"])
            )

            if edge_running:

                if confirm_callback:
                    res = confirm_callback(
                        self.texts.get("edge_open", "Microsoft Edge está abierto"),
                        self.texts.get("edge_open_confirm", "Edge needs to be closed to proceed. Close it?")
                    )

                    if not res:
                        return None
                else:
                    return None

                self.close_edge_processes()
                time.sleep(2)

            logger.info("🧩 Obteniendo cookie de Steam con Selenium (Edge)...")

            user_data_dir = ""

            if IS_WINDOWS:
                localapp = os.getenv("LOCALAPPDATA", "")
                user_data_dir = str(Path(localapp) / "Microsoft" / "Edge" / "User Data")

            elif IS_MACOS:
                user_data_dir = str(Path.home() / "Library" / "Application Support" / "Microsoft Edge")

            elif IS_LINUX:
                user_data_dir = str(Path.home() / ".config" / "microsoft-edge")

            service = EdgeService(executable_path=self.driver_path)

            options = Options()

            options.add_argument(f"--user-data-dir={user_data_dir}")
            options.add_argument(f"--profile-directory={profile_dir}")

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

                    if c.get("name") == "steamLoginSecure":

                        val = c.get("value")

                        save_cookie_to_env(val, ENV_PATH)

                        logger.info("✅ Cookie obtenida con Selenium.")

                        return val

                logger.warning("⚠️ No se encontró 'steamLoginSecure' en Selenium.")

            finally:
                driver.quit()

        except WebDriverException as e:

            msg = getattr(e, "msg", str(e))
            logger.error(f"❌ Selenium WebDriver error: {msg}")

            if "only supports Microsoft Edge version" in msg or "Unable to obtain driver for MicrosoftEdge" in msg:

                if _is_retry:
                    logger.error("❌ WebDriver ya intentó actualizarse.")
                    return None

                try:

                    from src.core.edge_updater import EdgeDriverUpdater

                    driver_updater = EdgeDriverUpdater(parent_widget=None)
                    driver_updater.update()

                    self.driver_path = str(ensure_driver_executable(DRIVER_PATH))

                    logger.info("🆗 WebDriver actualizado.")

                    return self.get_cookie_with_selenium(
                        headless=headless,
                        profile_dir=profile_dir,
                        confirm_callback=confirm_callback,
                        _is_retry=True
                    )

                except Exception as update_error:
                    logger.error(f"❌ Error actualizando WebDriver: {update_error}")

        except Exception as e:
            logger.error(f"⚠️ Error inesperado obteniendo cookie: {e}")

        return None

    def get_steam_cookie(self, confirm_callback: Optional[Callable[[str, str], bool]] = None) -> Optional[str]:

        if self.env_cookie:

            logger.info("🧩 Validando cookie desde .env...")

            if self.validar_cookie(self.env_cookie):
                return self.env_cookie

            logger.warning("⚠️ Cookie del .env inválida.")

        c = self.get_cookie_from_browser()

        if c and self.validar_cookie(c):
            return c

        if confirm_callback:
            if not confirm_callback("Cookie", self.texts.get("ask_cookie", "Obtain cookie via browser?")):
                return None

        c2 = self.get_cookie_with_selenium(headless=False, confirm_callback=confirm_callback)

        if c2 and self.validar_cookie(c2):
            return c2

        logger.error("❌ No se pudo obtener cookie de Steam.")
        return None

    def ask_and_obtain_cookie(self, confirm_callback: Callable[[str, str], bool]) -> Optional[str]:

        try:

            should = confirm_callback(
                "Cookie",
                self.texts.get(
                    "ask_cookie",
                    "The program will try to obtain your Steam cookie automatically.\n\nContinue?"
                ),
            )

            if not should:
                return None

            c = self.get_cookie_from_browser()

            if c and self.validar_cookie(c):
                return c

            c2 = self.get_cookie_with_selenium(headless=False, confirm_callback=confirm_callback)

            if c2 and self.validar_cookie(c2):
                return c2

            logger.warning("No se pudo obtener cookie automáticamente.")

            return None

        except Exception as e:

            logger.error(f"Error en ask_and_obtain_cookie: {e}")

            return None
