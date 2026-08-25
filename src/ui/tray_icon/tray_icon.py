import os
import logging
import webbrowser
# pyrefly: ignore [missing-import]
from PyQt5.QtWidgets import QSystemTrayIcon, QMenu, QApplication, QAction
# pyrefly: ignore [missing-import]
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor
# pyrefly: ignore [missing-import]
from PyQt5.QtCore import Qt

from src.core.utils import get_lang_from_registry, load_locale, LANG_DIR, IS_WINDOWS
from src.version import VERSION
from .constants import ASSETS_DIR
from .widgets import StatusWidgetAction, CustomMenuItemAction, SectionHeaderAction, VersionLabelAction
from .mixins import (CookieHandlerMixin, ForceGameHandlerMixin, IntegrityHandlerMixin,
                     NavigationHandlerMixin, UpdaterHandlerMixin, PresenceHandlerMixin)

try:
    LANG = get_lang_from_registry()
    TEXTS = load_locale(LANG)
except Exception:
    LANG = os.getenv('GEFORCE_LANG', 'en')
    TEXTS = load_locale(LANG)

logger = logging.getLogger('geforce_presence')

class SystemTrayIcon(QSystemTrayIcon,
                     CookieHandlerMixin,
                     ForceGameHandlerMixin,
                     IntegrityHandlerMixin,
                     NavigationHandlerMixin,
                     UpdaterHandlerMixin,
                     PresenceHandlerMixin):
                     
    def __init__(self, presence_manager, texts, config_manager, updater=None, parent=None):
        QSystemTrayIcon.__init__(self, parent)
        self.pm = presence_manager
        self.config_manager = config_manager
        self.updater = updater
        
        # Override TEXTS module-level if texts is passed, keeping it local/global-consistent
        global TEXTS
        TEXTS = texts
        self.texts = texts
        
        self.setIcon(QIcon(str(ASSETS_DIR / "geforce.ico")))
        self.setToolTip("GeForce NOW Presence")
        
        self.menu = QMenu(parent)
        
        # Apply dark theme / advanced visual stylesheet
        self.menu.setStyleSheet("""
            QMenu {
                background-color: #1e1f22; /* Discord-like dark background */
                color: #dcddde;            /* Light gray text */
                border: 1px solid #111111;
                border-radius: 8px;
                padding: 5px;
            }
            QMenu::item {
                background-color: transparent;
                padding: 8px 24px 8px 9px;
                border-radius: 4px;
                margin: 2px 4px;
                font-family: 'TT Octosquares Trl Cnd';
                font-size: 13px;
                color: #dcddde;
            }
            QMenu::icon {
                left: 4px;
            }
            QMenu::item:selected {
                background-color: #045D0E;
                color: white;
                font-weight: bold;
            }
            QMenu::separator {
                height: 1px;
                background: #3f4145;
                margin: 6px 8px;
            }
        """)
        
        self._reinstaller_worker = None
        self._repair_dialog = None
        self._download_progress_dlg = None
        self._download_cancelled = False
        self.status_action = None

        if self.updater:
            self.updater.update_status_changed.connect(self.update_menu)

        self.create_menu()
        if IS_WINDOWS:
            self.setContextMenu(self.menu)
        
        # Connect signals
        try:
            self.pm.request_match_selection.disconnect()
            self.pm.gfn_error_detected.disconnect()
            self.pm.download_progress.disconnect()
        except:
            pass
        self.pm.request_match_selection.connect(self.on_match_selection_requested)
        self.pm.gfn_error_detected.connect(self.on_gfn_error_detected)
        self.pm.download_progress.connect(self.on_download_progress)
        self.pm.presence_updated.connect(self.on_presence_updated)
        self.activated.connect(self.on_activated)
        self.menu.aboutToShow.connect(self.on_menu_show)
        self.menu.aboutToHide.connect(self.on_menu_hide)

    def create_menu(self):
        self.menu.clear()
        
        # Block 0: Status Widget
        forced = self.pm.forced_game
        active = self.pm.last_game
        
        if forced:
            state = "forced"
            gname = forced.get('name', 'Unknown')
            text = TEXTS.get("status_forced", "Forced: {game}").replace("{game}", gname)
        elif active and self.pm.rpc and getattr(self.pm, "_connected_client_id", None):
            state = "active"
            gname = active.get('name', 'Unknown')
            if gname == "GeForce NOW":
                text = TEXTS.get("status_searching", "Buscando juego...")
            else:
                text = TEXTS.get("status_active", "Active: {game}").replace("{game}", gname)
        else:
            state = "disconnected"
            text = TEXTS.get("status_disconnected", "Disconnected")
            
        discord_connected = self.pm.rpc is not None and getattr(self.pm, "_connected_client_id", None) is not None
        gfn_running = self.pm.is_geforce_running()
            
        if IS_WINDOWS:
            self.status_action = StatusWidgetAction(self.menu)
            self.status_action.update_status(state, text, discord_connected, gfn_running)
            self.menu.addAction(self.status_action)
        else:
            # Standard menu items for Linux/macOS
            status_text = f"Estado: {text}"
            status_action = self.menu.addAction(status_text)
            status_action.setEnabled(False)
            
            icon_map = {
                "active": "status-check.svg",
                "forced": "startup.svg",
                "disconnected": "status-failed.svg"
            }
            icon_file = icon_map.get(state)
            if icon_file:
                path = ASSETS_DIR / "iconos" / icon_file
                if path.exists():
                    status_action.setIcon(QIcon(str(path)))
            
            disc_status = "Discord: " + (TEXTS.get("status_connected", "Conectado") if discord_connected else TEXTS.get("status_disconnected", "Desconectado"))
            disc_action = self.menu.addAction(disc_status)
            disc_action.setEnabled(False)
            disc_icon = "status-check.svg" if discord_connected else "status-failed.svg"
            path = ASSETS_DIR / "iconos" / disc_icon
            if path.exists():
                disc_action.setIcon(QIcon(str(path)))
                
            gfn_status = "GFN: " + ("En ejecución" if gfn_running else "No iniciado")
            gfn_action = self.menu.addAction(gfn_status)
            gfn_action.setEnabled(False)
            gfn_icon = "status-check.svg" if gfn_running else "status-failed.svg"
            path = ASSETS_DIR / "iconos" / gfn_icon
            if path.exists():
                gfn_action.setIcon(QIcon(str(path)))

        self.menu.addSeparator()
        
        # Block 1: QUICK ACTION
        if IS_WINDOWS:
            self.menu.addAction(SectionHeaderAction(TEXTS.get("tray_sec_quick_action", "Acción Rápida"), self.menu))
        else:
            header = self.menu.addAction(TEXTS.get("tray_sec_quick_action", "Acción Rápida").upper())
            header.setEnabled(False)
        
        # 1.1 Force Game
        if IS_WINDOWS:
            force_text = TEXTS.get("tray_force_game", "Forzar juego...")
            force_action = CustomMenuItemAction(force_text, "crosshair.svg", parent=self.menu)
            force_action.triggered.connect(self.toggle_force_game)
            self.menu.addAction(force_action)
            
            # 1.2 Open GeForce NOW
            open_gfn_text = TEXTS.get("tray_open_gfn", "Abrir GeForce NOW")
            open_gfn_action = CustomMenuItemAction(open_gfn_text, "nvidia-color.svg", parent=self.menu)
            open_gfn_action.triggered.connect(self.open_geforce)
            self.menu.addAction(open_gfn_action)

            # 1.3 Open Discord
            open_discord_text = TEXTS.get("tray_open_discord", "Abrir Discord")
            open_discord_action = CustomMenuItemAction(open_discord_text, "discord-color.svg", parent=self.menu)
            open_discord_action.triggered.connect(self.open_discord)
            self.menu.addAction(open_discord_action)
        
        # 1.4 Get Steam cookie
        cookie_text = TEXTS.get("tray_get_cookie", "Obtener cookie de Steam")
        if IS_WINDOWS:
            cookie_action = CustomMenuItemAction(cookie_text, "steam-color.svg", parent=self.menu)
            cookie_action.triggered.connect(self.obtain_cookie)
            self.menu.addAction(cookie_action)
        else:
            cookie_action = self.menu.addAction(cookie_text)
            path = ASSETS_DIR / "iconos" / "steam-color.svg"
            if path.exists():
                cookie_action.setIcon(QIcon(str(path)))
            cookie_action.triggered.connect(self.obtain_cookie)
        
        self.menu.addSeparator()
        
        # Block 2: CUSTOM PRESENCE (Only if game active)
        active_game = self.pm.forced_game or self.pm.last_game
        if active_game:
            if IS_WINDOWS:
                self.menu.addAction(SectionHeaderAction(TEXTS.get("tray_sec_custom_presence", "Presencia Personalizada"), self.menu))
            else:
                header = self.menu.addAction(TEXTS.get("tray_sec_custom_presence", "Presencia Personalizada").upper())
                header.setEnabled(False)
            
            gname = active_game.get("name", "Unknown")
            if len(gname) > 20: gname = gname[:17] + "..."
            
            cp_text = f"Custom Presence: {gname}"
            if IS_WINDOWS:
                cp_action = CustomMenuItemAction(cp_text, "target.svg", "chevron-right.svg", parent=self.menu)
                cp_action.triggered.connect(self.open_custom_presence_dialog)
                self.menu.addAction(cp_action)
            else:
                cp_action = self.menu.addAction(cp_text)
                path = ASSETS_DIR / "iconos" / "target.svg"
                if path.exists():
                    cp_action.setIcon(QIcon(str(path)))
                cp_action.triggered.connect(self.open_custom_presence_dialog)
            self.menu.addSeparator()
            
        # Block 3: TOOLS
        if IS_WINDOWS:
            self.menu.addAction(SectionHeaderAction(TEXTS.get("tray_sec_tools", "Herramientas"), self.menu))
        else:
            header = self.menu.addAction(TEXTS.get("tray_sec_tools", "Herramientas").upper())
            header.setEnabled(False)
        
        # 3.1 View logs
        logs_text = TEXTS.get("tray_tools_logs", "Ver logs")
        if IS_WINDOWS:
            logs_action = CustomMenuItemAction(logs_text, "gear.svg", parent=self.menu)
            logs_action.triggered.connect(self.open_logs)
            self.menu.addAction(logs_action)
        else:
            logs_action = self.menu.addAction(logs_text)
            path = ASSETS_DIR / "iconos" / "gear.svg"
            if path.exists():
                logs_action.setIcon(QIcon(str(path)))
            logs_action.triggered.connect(self.open_logs)

        # 3.2 Verify integrity
        if IS_WINDOWS:
            integrity_text = TEXTS.get("tray_tools_integrity", "Verificar integridad")
            integrity_action = CustomMenuItemAction(integrity_text, "activity.svg", parent=self.menu)
            integrity_action.triggered.connect(self.verify_integrity)
            self.menu.addAction(integrity_action)

        # 3.3 Join Discord
        invite_text = TEXTS.get("tray_discord_invite_gfn", "Entra al servidor de GeForce NOW")
        if IS_WINDOWS:
            invite_action = CustomMenuItemAction(invite_text, "discord.svg", parent=self.menu)
            invite_action.triggered.connect(lambda: webbrowser.open("https://discord.gg/kHUvndZnw7"))
            self.menu.addAction(invite_action)
        else:
            invite_action = self.menu.addAction(invite_text)
            path = ASSETS_DIR / "iconos" / "discord.svg"
            if path.exists():
                invite_action.setIcon(QIcon(str(path)))
            invite_action.triggered.connect(lambda: webbrowser.open("https://discord.gg/kHUvndZnw7"))

        # 3.4 Startup Preferences Submenu
        startup_menu = QMenu(TEXTS.get("tray_startup_options", "Preferencias"), self.menu)
        icon_pixmap = QPixmap(str(ASSETS_DIR / "iconos" / "startup.svg")).scaled(16, 16, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        startup_menu.setIcon(QIcon(icon_pixmap))
        startup_menu.setStyleSheet(self.menu.styleSheet())
        
        # 1. Start with Windows
        if IS_WINDOWS:
            self.opt_start_windows = startup_menu.addAction(TEXTS.get("config_start_windows", "Iniciar con Windows"))
            self.opt_start_windows.setCheckable(True)
            self.opt_start_windows.setChecked(self.config_manager.get_setting("start_with_windows", False))
            self.opt_start_windows.triggered.connect(self.toggle_start_with_windows)
            
            # 2. Start GFN on Launch
            self.opt_start_gfn = startup_menu.addAction(TEXTS.get("config_start_gfn", "Iniciar GeForce NOW al abrir"))
            self.opt_start_gfn.setCheckable(True)
            self.opt_start_gfn.setChecked(self.config_manager.get_setting("start_gfn_on_launch", True))
            self.opt_start_gfn.triggered.connect(lambda checked: self.config_manager.set_setting("start_gfn_on_launch", checked))
            
            # 3. Start Discord on Launch
            self.opt_start_discord = startup_menu.addAction(TEXTS.get("config_start_discord", "Iniciar Discord al abrir"))
            self.opt_start_discord.setCheckable(True)
            self.opt_start_discord.setChecked(self.config_manager.get_setting("start_discord_on_launch", False))
            self.opt_start_discord.triggered.connect(lambda checked: self.config_manager.set_setting("start_discord_on_launch", checked))
        
        # 4. Get Cookie on Launch
        self.opt_get_cookie = startup_menu.addAction(TEXTS.get("config_get_cookie", "Obtener cookie al iniciar la aplicación"))
        self.opt_get_cookie.setCheckable(True)
        self.opt_get_cookie.setChecked(self.config_manager.get_setting("get_cookie_on_launch", False))
        self.opt_get_cookie.triggered.connect(lambda checked: self.config_manager.set_setting("get_cookie_on_launch", checked))
        
        # 5. Show Lobby Status
        self.opt_show_lobby = startup_menu.addAction(TEXTS.get("config_show_lobby", "Mostrar GeForce NOW cuando no hay juego activo"))
        self.opt_show_lobby.setCheckable(True)
        self.opt_show_lobby.setChecked(self.config_manager.get_setting("show_lobby_status", True))
        self.opt_show_lobby.triggered.connect(lambda checked: self.config_manager.set_setting("show_lobby_status", checked))
        
        self.menu.addMenu(startup_menu)
        
        # 3.5 Language Submenu
        lang_menu = QMenu(TEXTS.get("tray_language", "Idioma"), self.menu)
        lang_pixmap = QPixmap(str(ASSETS_DIR / "iconos" / "sync.svg")).scaled(16, 16, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        
        # Tint language icon to #b0b3b8 to match the other unhovered icons
        tinted_pixmap = QPixmap(lang_pixmap.size())
        tinted_pixmap.fill(Qt.transparent)
        painter = QPainter(tinted_pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.drawPixmap(0, 0, lang_pixmap)
        painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        painter.fillRect(tinted_pixmap.rect(), QColor("#b0b3b8"))
        painter.end()
        
        lang_menu.setIcon(QIcon(tinted_pixmap))
        lang_menu.setStyleSheet(self.menu.styleSheet())
        
        available_langs = self.get_available_languages()
        current_lang = LANG
        
        for code, name in available_langs.items():
            action = lang_menu.addAction(name)
            action.setCheckable(True)
            action.setChecked(code == current_lang)
            action.triggered.connect(lambda checked, c=code: self.change_language(c))
            
        self.menu.addMenu(lang_menu)
        
        self.menu.addSeparator()
        
        # Block 4: Footer Actions
        # 4.1 Check updates
        update_text = TEXTS.get("tray_check_updates", "Buscar actualizaciones")
        if IS_WINDOWS:
            update_action = CustomMenuItemAction(update_text, "update.svg", parent=self.menu)
            update_action.triggered.connect(self.manual_check_updates)
            self.menu.addAction(update_action)
        else:
            update_action = self.menu.addAction(update_text)
            path = ASSETS_DIR / "iconos" / "update.svg"
            if path.exists():
                update_action.setIcon(QIcon(str(path)))
            update_action.triggered.connect(self.manual_check_updates)
        
        # 4.2 About
        about_text = TEXTS.get("tray_about", "Acerca de")
        if IS_WINDOWS:
            about_action = CustomMenuItemAction(about_text, "info.svg", parent=self.menu)
            about_action.triggered.connect(self.open_about)
            self.menu.addAction(about_action)
        else:
            about_action = self.menu.addAction(about_text)
            path = ASSETS_DIR / "iconos" / "info.svg"
            if path.exists():
                about_action.setIcon(QIcon(str(path)))
            about_action.triggered.connect(self.open_about)
        
        self.menu.addSeparator()
        
        # 4.3 Exit
        exit_text = TEXTS.get("tray_exit", "Salir")
        if IS_WINDOWS:
            exit_action = CustomMenuItemAction(exit_text, "can.svg", is_danger=True, parent=self.menu)
            exit_action.triggered.connect(QApplication.instance().quit)
            self.menu.addAction(exit_action)
        else:
            exit_action = self.menu.addAction(exit_text)
            path = ASSETS_DIR / "iconos" / "can.svg"
            if path.exists():
                exit_action.setIcon(QIcon(str(path)))
            exit_action.triggered.connect(QApplication.instance().quit)
 
        # 4.4 Version
        version_text = VERSION if VERSION.startswith("v") else f"{VERSION}"
        if IS_WINDOWS:
            version_action = VersionLabelAction(version_text, parent=self.menu)
            self.menu.addAction(version_action)
        else:
            version_action = self.menu.addAction(version_text)
            version_action.setEnabled(False)

    def update_menu(self):
        self.create_menu()

    def on_activated(self, reason):
        if not IS_WINDOWS and reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.Context):
            from PyQt5.QtGui import QCursor
            self.menu.popup(QCursor.pos())
        elif reason == QSystemTrayIcon.DoubleClick:
            from PyQt5.QtGui import QCursor
            self.menu.popup(QCursor.pos())

    def toggle_start_with_windows(self, checked):
        from src.core.utils import set_autostart_windows
        self.config_manager.set_setting("start_with_windows", checked)
        try:
            set_autostart_windows(checked)
            if checked:
                from src.core.utils import is_startup_disabled_in_task_manager
                if is_startup_disabled_in_task_manager():
                    from src.ui.dialogs import GamingMessageBox
                    GamingMessageBox.show_warning(
                        None,
                        TEXTS.get("tray_title", "GeForce NOW Presence"),
                        TEXTS.get("startup_disabled_in_tm", "Deshabilitado en Administrador de tareas")
                    )
        except Exception as e:
            logger.error(f"Error toggling startup shortcut: {e}")

    def get_available_languages(self):
        available = {}
        lang_mapping = {
            "en": "English",
            "es": "Español",
            "ru": "Русский"
        }
        try:
            for p in LANG_DIR.glob("*.json"):
                code = p.stem.lower()
                available[code] = lang_mapping.get(code, code.capitalize())
        except Exception as e:
            logger.error(f"Error listing available languages: {e}")
            available = {"en": "English", "es": "Español", "ru": "Русский"}
        return available

    def change_language(self, lang_code):
        from src.core.utils import get_lang_from_registry
        current_lang = get_lang_from_registry()
        
        if lang_code == current_lang:
            return
            
        available_langs = self.get_available_languages()
        lang_name = available_langs.get(lang_code, lang_code.upper())
        
        from src.ui.dialogs import GamingMessageBox
        title = TEXTS.get("restart_confirm_title", "Cambiar idioma")
        msg = TEXTS.get("restart_confirm_msg", "¿Quieres cambiar el idioma a {lang_name} y reiniciar la aplicación ahora?").replace("{lang_name}", lang_name)
        
        if GamingMessageBox.show_question(None, title, msg):
            from src.core.utils import save_lang_to_registry
            save_lang_to_registry(lang_code)
            self.restart_application()

    def restart_application(self):
        import sys
        import subprocess
        
        logger.info("Reinicio solicitado por cambio de idioma...")
        
        try:
            if self.pm:
                self.pm.stop_monitoring()
                self.pm.close_fake_executable()
                self.pm.close()
        except Exception as e:
            logger.error(f"Error stopping presence manager during restart: {e}")
            
        try:
            from src.core.utils import release_lock
            release_lock()
        except Exception as e:
            logger.error(f"Error releasing lock: {e}")
            
        try:
            new_args = []
            skip_next = False
            for arg in sys.argv[1:]:
                if skip_next:
                    skip_next = False
                    continue
                if arg == "--delay":
                    skip_next = True
                    continue
                if arg.startswith("--delay="):
                    continue
                new_args.append(arg)
                
            if getattr(sys, "frozen", False):
                subprocess.Popen([sys.executable] + new_args)
            else:
                subprocess.Popen([sys.executable, "-m", "src.GeForceNOWRichPresence"] + new_args)
        except Exception as e:
            logger.error(f"Error spawning new instance: {e}")
            
        QApplication.instance().quit()
