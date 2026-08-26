import os
import logging
import requests
from typing import Optional, Dict

from src.core.utils import save_cookie_to_env, ENV_PATH

logger = logging.getLogger('geforce_presence')

class CookieManager:
    """
    Gestor de autenticación y validación de la cookie de Steam (steamLoginSecure).
    """
    def __init__(self, texts: Dict, env_cookie: Optional[str] = None, test_url: str = "", config_manager=None):
        self.texts = texts
        self.env_cookie = env_cookie
        self.test_url = test_url or "https://steamcommunity.com/dev/testrichpresence"
        self.config_manager = config_manager

    def validar_cookie(self, cookie_value: str) -> bool:
        """
        Valida si la cookie 'steamLoginSecure' sigue siendo válida consultando
        la API/página de desarrollo de Steam Community.
        """
        if not cookie_value or not cookie_value.strip():
            return False

        try:
            s = requests.Session()
            # Asegurar headers estándar de navegador para evitar bloqueos
            s.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            })
            s.cookies.set('steamLoginSecure', cookie_value.strip(), domain='steamcommunity.com')
            r = s.get(self.test_url, timeout=10, allow_redirects=True)
            
            if r.status_code == 200 and "Sign In" not in r.text and "login" not in r.url.lower():
                return True
        except Exception as e:
            logger.debug(f"Error validando cookie de Steam: {e}")
        return False

    def get_steam_cookie(self, confirm_callback: Optional[callable] = None) -> Optional[str]:
        """
        Obtiene y valida la cookie configurada actualmente en el entorno (.env).
        """
        if self.env_cookie:
            logger.info("🧩 Validando cookie de Steam desde .env...")
            if self.validar_cookie(self.env_cookie):
                logger.info("✅ Cookie del .env válida.")
                return self.env_cookie
            else:
                logger.warning("⚠️ Cookie del .env expirada o inválida.")
        return None

    def save_cookie(self, cookie_value: str) -> bool:
        """
        Valida y guarda la cookie en el archivo .env si es correcta.
        """
        clean_cookie = cookie_value.strip()
        if self.validar_cookie(clean_cookie):
            save_cookie_to_env(clean_cookie, ENV_PATH)
            self.env_cookie = clean_cookie
            logger.info("✅ Cookie de Steam guardada y validada exitosamente en .env.")
            return True
        return False
