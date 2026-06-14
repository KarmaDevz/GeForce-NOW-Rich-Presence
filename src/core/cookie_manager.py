import os
import time
import logging
import requests
import psutil
import subprocess
from pathlib import Path
from typing import Optional, Callable, Dict, Tuple

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
    def __init__(self, texts: Dict, env_cookie: Optional[str] = None, test_url: str = "", config_manager=None):
        self.texts = texts
        self.env_cookie = env_cookie
        self.test_url = test_url
        self.config_manager = config_manager
        self.driver_path = str(ensure_driver_executable(DRIVER_PATH))

    def validar_cookie(self, cookie_value: str) -> bool:
        try:
            s = requests.Session()
            s.cookies.set('steamLoginSecure', cookie_value, domain='steamcommunity.com')
            r = s.get(self.test_url, timeout=10)
            if r.status_code == 200 and "Sign In" not in r.text and "login" not in r.url.lower():
                return True
        except Exception as e:
            logger.debug(f"Error validando cookie: {e}")
        return False

    def get_cookie_from_browser_profiles(self) -> Tuple[Optional[str], Optional[str], bool]:
        """
        Recopila todas las cookies de Steam de los perfiles locales y luego las valida.
        Retorna (cookie_value, browser_name, has_expired_candidates).
        """
        if not browser_cookie3:
            logger.warning("browser_cookie3 no instalado.")
            return None, None, False
            
        logger.info("🧩 Intentando recopilar cookies de Steam desde perfiles de navegadores locales...")
        candidates = []
        
        browsers_to_try = []
        for name in ['edge', 'chrome', 'firefox', 'brave', 'opera', 'vivaldi']:
            fn = getattr(browser_cookie3, name, None)
            if fn:
                browsers_to_try.append((name.capitalize(), fn))
                
        # 1. Recopilar candidatos de forma segura e independiente por navegador
        for b_name, get_cookies_fn in browsers_to_try:
            try:
                logger.debug(f"Buscando cookies de Steam en {b_name}...")
                cj = get_cookies_fn(domain_name='steamcommunity.com')
                found_in_browser = False
                for cookie in cj:
                    if cookie.name == 'steamLoginSecure' and cookie.value:
                        candidates.append((cookie.value, b_name))
                        found_in_browser = True
                if found_in_browser:
                    logger.debug(f"Candidato encontrado en {b_name}.")
            except Exception as e:
                logger.debug(f"Extracción de cookies falló para {b_name}: {e}")
                
        # 2. Validar candidatos recopilados
        has_expired = False
        for cookie_val, b_name in candidates:
            logger.info(f"Validando cookie candidata de {b_name}...")
            if self.validar_cookie(cookie_val):
                logger.info(f"✅ Cookie válida obtenida desde {b_name}.")
                return cookie_val, b_name, has_expired
            else:
                logger.info(f"❌ Cookie de {b_name} expirada o inválida.")
                has_expired = True
                
        logger.info("⚠️ No se encontraron cookies válidas en los perfiles locales.")
        return None, None, has_expired
    
    def close_browser_processes(self, browser: str = "edge"):
        """Cierra todos los procesos del navegador especificado."""
        proc_name = "msedge.exe" if browser.lower() == "edge" else "chrome.exe"
        closed = 0
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if proc.info['name'] and proc_name in proc.info['name'].lower():
                    proc.terminate()
                    closed += 1
            except Exception:
                continue
        if closed:
            logger.info(f"🔒 {closed} procesos de {browser} terminados.")
        else:
            logger.debug(f"No había procesos de {browser} en ejecución.")

    def has_visible_windows(self, browser: str) -> bool:
        """Comprueba si el navegador especificado tiene ventanas visibles abiertas."""
        proc_name = "msedge.exe" if browser.lower() == "edge" else "chrome.exe"
        pids = set()
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if proc.info['name'] and proc_name in proc.info['name'].lower():
                    pids.add(proc.info['pid'])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
                
        if not pids:
            return False
            
        if IS_WINDOWS:
            try:
                import win32gui
                import win32process
            except ImportError:
                return True
                
            visible_windows = []
            def enum_windows_callback(hwnd, extra):
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    if title:
                        _, win_pid = win32process.GetWindowThreadProcessId(hwnd)
                        if win_pid in pids:
                            visible_windows.append(hwnd)
                return True
            try:
                win32gui.EnumWindows(enum_windows_callback, None)
                return len(visible_windows) > 0
            except Exception as e:
                logger.debug(f"Error enumerando ventanas en Windows: {e}")
                return True
                
        elif IS_MACOS:
            app_name = "Microsoft Edge" if browser.lower() == "edge" else "Google Chrome"
            script = f'''
            tell application "System Events"
                if exists process "{app_name}" then
                    tell application "{app_name}" to get count of windows
                else
                    return 0
                end if
            end tell
            '''
            try:
                result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    count = int(result.stdout.strip())
                    return count > 0
            except Exception as e:
                logger.debug(f"Error comprobando ventanas en macOS: {e}")
            return True
            
        else:
            return True

    def get_cookie_with_selenium(self, 
                                 browser: str = "edge",
                                 headless: bool = False, 
                                 profile_dir: str = "Default", 
                                 confirm_callback: Optional[Callable[[str, str], bool]] = None,
                                 _is_retry: bool = False) -> Optional[str]:
        try:
            # Check if browser is running
            proc_name = "msedge.exe" if browser.lower() == "edge" else "chrome.exe"
            pids = set()
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if proc.info['name'] and proc_name in proc.info['name'].lower():
                        pids.add(proc.info['pid'])
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            browser_running = len(pids) > 0

            if browser_running:
                has_window = self.has_visible_windows(browser)
                if has_window:
                    if confirm_callback:
                        browser_display = "Microsoft Edge" if browser.lower() == "edge" else "Google Chrome"
                        res = confirm_callback(
                            self.texts.get("edge_open", f"{browser_display} está abierto"), 
                            self.texts.get('edge_open_confirm', f"{browser_display} needs to be closed to proceed. Close it?")
                        )
                        if not res:
                            logger.info(f"⏭️ Usuario canceló la obtención de cookie porque {browser_display} estaba abierto.")
                            return None
                    else:
                        logger.info(f"{browser} is running with a window and no callback provided to confirm close.")
                        return None

                self.close_browser_processes(browser)
                time.sleep(2)

            logger.info(f"🧩 Obteniendo cookie de Steam con Selenium ({browser}, headless={headless})...")
            
            user_data_dir = ""
            if IS_WINDOWS:
                localapp = os.getenv("LOCALAPPDATA", "")
                if browser.lower() == "edge":
                    user_data_dir = str(Path(localapp) / "Microsoft" / "Edge" / "User Data")
                else:
                    user_data_dir = str(Path(localapp) / "Google" / "Chrome" / "User Data")
            elif IS_MACOS:
                if browser.lower() == "edge":
                    user_data_dir = str(Path.home() / "Library" / "Application Support" / "Microsoft Edge")
                else:
                    user_data_dir = str(Path.home() / "Library" / "Application Support" / "Google" / "Chrome")
            elif IS_LINUX:
                if browser.lower() == "edge":
                    user_data_dir = str(Path.home() / ".config" / "microsoft-edge")
                else:
                    user_data_dir = str(Path.home() / ".config" / "google-chrome")

            if not user_data_dir or not Path(user_data_dir).exists():
                logger.error(f"❌ No se encontró la carpeta de perfiles de {browser} en: {user_data_dir}")

            if browser.lower() == "edge":
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
            else:
                from selenium.webdriver.chrome.options import Options as ChromeOptions
                options = ChromeOptions()
                options.add_argument(f"--user-data-dir={user_data_dir}")
                options.add_argument(f"--profile-directory={profile_dir}")
                options.add_argument("--no-sandbox")
                options.add_argument("--disable-dev-shm-usage")
                options.add_argument("--disable-gpu")
                if headless:
                    options.add_argument("--headless=new")
                driver = webdriver.Chrome(options=options)

            try:
                driver.get("https://steamcommunity.com")
                
                # Polling loop para esperar que se registre la cookie (hasta 15 segundos)
                cookie_val = None
                for _ in range(15):
                    cookies = driver.get_cookies()
                    for c in cookies:
                        if c.get('name') == 'steamLoginSecure':
                            cookie_val = c.get('value')
                            break
                    if cookie_val:
                        break
                    time.sleep(1)

                if cookie_val:
                    save_cookie_to_env(cookie_val, ENV_PATH)
                    logger.debug(f"Cookie obtenida parcial: {cookie_val[:20]}... (longitud: {len(cookie_val)})")
                    logger.info(f"✅ Cookie obtenida con Selenium ({browser}).")
                    return cookie_val
                logger.warning("⚠️ No se encontró 'steamLoginSecure' en la sesión de Steam.")
            finally:
                driver.quit()
                
        except WebDriverException as e:
            msg = getattr(e, "msg", str(e))
            logger.error(f"❌ Selenium WebDriver error: {msg}")

            if browser.lower() == "edge" and ("only supports Microsoft Edge version" in msg or "Unable to obtain driver for MicrosoftEdge" in msg):
                if _is_retry:
                    logger.error("❌ Ya se intentó actualizar el WebDriver y falló. Abortando.")
                    return None

                logger.warning("🔄 Edge WebDriver desactualizado. Intentando actualizar...")
                try:
                    from src.core.edge_updater import EdgeDriverUpdater
                    driver_updater = EdgeDriverUpdater(parent_widget=None)
                    driver_updater.update()
                    
                    self.driver_path = str(ensure_driver_executable(DRIVER_PATH))
                    logger.info("🆗 WebDriver actualizado. Reintentando...")
                    return self.get_cookie_with_selenium(
                        browser=browser,
                        headless=headless,
                        profile_dir=profile_dir,
                        confirm_callback=confirm_callback,
                        _is_retry=True
                    )
                except Exception as update_error:
                    logger.error(f"❌ Error actualizando Edge WebDriver: {update_error}")
            else:
                logger.error("⚠️ Error de Selenium no relacionado con el driver desactualizado.")
        except Exception as e:
            logger.error(f"⚠️ Error inesperado obteniendo cookie con Selenium: {e}")
        return None

    def get_steam_cookie(self, confirm_callback: Optional[Callable[[str, str], bool]] = None) -> Optional[str]:
        if self.env_cookie:
            logger.info("🧩 Validando cookie desde .env...")
            if self.validar_cookie(self.env_cookie):
                logger.info("✅ Cookie del .env válida (Origen: .env).")
                return self.env_cookie
            else:
                logger.warning("⚠️ Cookie del .env expirada o inválida.")

        c, browser_name, has_expired = self.get_cookie_from_browser_profiles()
        if c:
            return c

        if confirm_callback:
             if not confirm_callback("Cookie", self.texts.get('ask_cookie', 'Obtain cookie via Edge?')):
                 return None

             # Intentar Selenium en modo oculto (headless) primero
             c2 = self.get_cookie_with_selenium(browser="edge", headless=True, confirm_callback=confirm_callback)
             if c2 and self.validar_cookie(c2):
                 return c2

             # Fallback a Selenium modo visual
             c2 = self.get_cookie_with_selenium(browser="edge", headless=False, confirm_callback=confirm_callback)
             if c2 and self.validar_cookie(c2):
                 return c2

        logger.error("❌ No se pudo obtener cookie de Steam automáticamente.")
        return None

    def ask_and_obtain_cookie(self, confirm_callback: Callable[[str, str], bool]) -> Tuple[Optional[str], str]:
        """
        Versión interactiva para la interfaz de usuario.
        Retorna una tupla (cookie_value, status_key).
        """
        try:
            should = confirm_callback("Cookie", 
                                self.texts.get('ask_cookie', 'The program will try to obtain your Steam cookie using Microsoft Edge. Make sure you are logged in to Steam in Edge.\n\nDo you want to continue?'))

            if not should:
                logger.info("No se obtuvo cookie de Steam de forma interactiva.")
                return None, "cookie_err_cancelled"

            # 1. Intentar leer de perfiles locales (rápido y no invasivo)
            c, browser_name, has_expired = self.get_cookie_from_browser_profiles()
            if c:
                save_cookie_to_env(c, ENV_PATH)
                logger.info(f"Cookie guardada en .env desde perfiles (Origen: {browser_name})")
                return c, "cookie_saved"

            # 2. Intentar Selenium Headless (oculto)
            logger.info("Intentando obtener cookie con Selenium en modo oculto (headless)...")
            c2 = self.get_cookie_with_selenium(browser="edge", headless=True, confirm_callback=confirm_callback)
            if c2 and self.validar_cookie(c2):
                logger.info("Cookie guardada en .env desde Selenium Headless")
                return c2, "cookie_saved"

            # 3. Intentar Selenium Visual
            logger.info("Modo oculto falló. Intentando con Selenium en modo visual...")
            c2 = self.get_cookie_with_selenium(browser="edge", headless=False, confirm_callback=confirm_callback)
            if c2 and self.validar_cookie(c2):
                logger.info("Cookie guardada en .env desde Selenium Visual")
                return c2, "cookie_saved"

            if has_expired:
                return None, "cookie_err_expired"
            else:
                return None, "cookie_err_not_found"
            
        except Exception as e:
            logger.error(f"Error en ask_and_obtain_cookie: {e}")
            return None, "cookie_err_headless"
