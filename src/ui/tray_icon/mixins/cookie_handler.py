import os
import logging
from typing import TYPE_CHECKING
from PyQt5.QtWidgets import QSystemTrayIcon

from src.ui.dialogs import GamingMessageBox, GamingTextInputDialog
from src.core.utils import get_lang_from_registry, load_locale, save_cookie_to_env, ENV_PATH

try:
    LANG = get_lang_from_registry()
    TEXTS = load_locale(LANG)
except Exception:
    LANG = os.getenv('GEFORCE_LANG', 'en')
    TEXTS = load_locale(LANG)

logger = logging.getLogger('geforce_presence')

if TYPE_CHECKING:
    from ..tray_icon import SystemTrayIcon
    Base = SystemTrayIcon
else:
    Base = object

class CookieHandlerMixin(Base):
    """
    Mixin para la gestión manual y validación de la cookie de Steam en la bandeja del sistema.
    """
    def obtain_cookie(self):
        current_cookie = self.pm.cookie_manager.env_cookie or ""
        
        cookie_val, ok = GamingTextInputDialog.get_text(
            None,
            TEXTS.get("cookie_manual_title", "Configuración de Cookie de Steam"),
            TEXTS.get("cookie_manual_label", "Pega el valor de tu cookie 'steamLoginSecure':"),
            current_cookie
        )

        if not ok:
            logger.info("El usuario canceló el diálogo de configuración de cookie.")
            return

        clean_cookie = cookie_val.strip()
        if not clean_cookie:
            # Si el usuario borró la cookie existente
            if current_cookie:
                save_cookie_to_env("", ENV_PATH)
                self.pm.cookie_manager.env_cookie = None
                self.pm.update_cookie(None)
                logger.info("Cookie de Steam eliminada de la configuración.")
                self.showMessage(
                    TEXTS.get("cookie_title", "Cookie"),
                    TEXTS.get("cookie_removed", "Cookie de Steam eliminada."),
                    QSystemTrayIcon.Information,
                    3000
                )
            return

        # Validar la cookie contra los servidores de Steam
        if self.pm.cookie_manager.validar_cookie(clean_cookie):
            save_cookie_to_env(clean_cookie, ENV_PATH)
            self.pm.cookie_manager.env_cookie = clean_cookie
            self.pm.update_cookie(clean_cookie)
            logger.info("✅ Cookie de Steam configurada y validada exitosamente.")
            self.showMessage(
                TEXTS.get("cookie_title", "Cookie"),
                TEXTS.get("cookie_saved", "Cookie de Steam guardada y validada exitosamente."),
                QSystemTrayIcon.Information,
                3000
            )
        else:
            logger.warning("❌ La cookie de Steam ingresada no es válida o ha expirado.")
            GamingMessageBox.show_warning(
                None,
                TEXTS.get("cookie_title", "Cookie"),
                TEXTS.get("cookie_invalid_msg", "La cookie introducida es inválida o ha expirado. Por favor, compruébala e inténtalo de nuevo.")
            )
