import os
from typing import TYPE_CHECKING
from PyQt5.QtWidgets import QSystemTrayIcon, QDialog

from src.core.utils import get_lang_from_registry, load_locale, IS_LINUX
from ..dialogs import CustomPresenceDialog, MatchSelectionDialog

try:
    LANG = get_lang_from_registry()
    TEXTS = load_locale(LANG)
except Exception:
    LANG = os.getenv('GEFORCE_LANG', 'en')
    TEXTS = load_locale(LANG)

if TYPE_CHECKING:
    from ..tray_icon import SystemTrayIcon
    Base = SystemTrayIcon
else:
    Base = object

class PresenceHandlerMixin(Base):
    def open_custom_presence_dialog(self):
        game = self.pm.forced_game or self.pm.last_game
        if not game:
            self.showMessage("Error", "No hay juego activo.", QSystemTrayIcon.Warning)
            return
            
        name = game.get("name", "Unknown")
        dlg = CustomPresenceDialog(name, game, parent=None)
        if dlg.exec_() == QDialog.Accepted and dlg.result_data:
            self.pm.set_custom_presence(dlg.result_data)
            self.showMessage("Custom Presence", f"Presencia actualizada para {name}", QSystemTrayIcon.Information, 2000)

    def on_presence_updated(self, state, text, discord_connected=False, gfn_running=False):
        if getattr(self, "status_action", None):
            try:
                self.status_action.update_status(state, text, discord_connected, gfn_running)
            except RuntimeError:
                pass

    def on_menu_show(self):
        # On Linux a rebuild gives every item a new DBusMenu ID and the tray host
        # swaps the whole menu while it opens, so only rebuild when something changed
        if not IS_LINUX or self._menu_state_key() != getattr(self, "_menu_key", None):
            self.update_menu()
        if getattr(self, "status_action", None):
            self.status_action.start_animation()

    def on_menu_hide(self):
        if getattr(self, "status_action", None):
            self.status_action.stop_animation()

    def on_match_selection_requested(self, game_key, candidates):
        dialog = MatchSelectionDialog(game_key, candidates)
        if dialog.exec_() == QDialog.Accepted:
            self.pm.on_match_selected(game_key, dialog.selected_match)
        else:
            self.pm.on_match_selected(game_key, None)
