import logging
import threading
import time
import os
import subprocess
import sys
from PyQt5.QtWidgets import QSystemTrayIcon, QMenu, QAction, QApplication, QMessageBox, QProgressDialog
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QDialog
from src.core.utils import ASSETS_DIR, LOG_FILE, set_autostart_windows, IS_WINDOWS, IS_LINUX, IS_MACOS
from src.core.app_launcher import AppLauncher
from src.ui.dialogs import AskGameDialog, MatchSelectionDialog, GamingMessageBox, GamingInputDialog, QuestListDialog, CustomPresenceDialog, AboutDialog, GFNRepairDialog, GAMING_STYLESHEET
from src.core.utils import get_lang_from_registry, load_locale
from src.core.reinstaller import GFNReinstallerWorker

try:
    LANG = get_lang_from_registry()
    TEXTS = load_locale(LANG)
except Exception:
    LANG = os.getenv('GEFORCE_LANG', 'en')
    TEXTS = load_locale(LANG)

logger = logging.getLogger('geforce_presence')

class SystemTrayIcon(QSystemTrayIcon):
    def __init__(self, presence_manager, texts, config_manager, parent=None):
        super().__init__(parent)
        self.pm = presence_manager
        self.config_manager = config_manager
        TEXTS = texts
        
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
                padding: 8px 24px 8px 12px;
                border-radius: 4px;
                margin: 2px 4px;
            }
            QMenu::item:selected {
                background-color: #045D0E; /* Discord Blurple */
                color: white;
            }
            QMenu::separator {
                height: 1px;
                background: #3f4145;
                margin: 6px 8px;
            }
        """)

        
        self._reinstaller_worker = None
        self._repair_dialog = None

        self.create_menu()
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
        self.activated.connect(self.on_activated)
        self.menu.aboutToShow.connect(self.update_menu)

    def create_menu(self):
        self.menu.clear()
        
        # Force Game
        force_text = TEXTS.get("tray_force_game", "Force game...")
        if self.pm.forced_game:
            game_name = self.pm.forced_game.get('name', 'Unknown')
            if len(game_name) > 20:
                game_name = game_name[:17] + "..."
            force_text = f"Stop forcing: {game_name}"
            
        force_action = QAction(force_text, self.menu)
        force_action.triggered.connect(self.toggle_force_game)
        self.menu.addAction(force_action)
        
        # Obtain Cookie
        cookie_action = QAction(TEXTS.get("tray_get_cookie", "Obtain Steam cookie"), self.menu)
        cookie_action.triggered.connect(self.obtain_cookie)
        self.menu.addAction(cookie_action)
        
        # Open GeForce
        open_gf_action = QAction(TEXTS.get("tray_open_geforce", "Open GeForce NOW"), self.menu)
        open_gf_action.triggered.connect(self.open_geforce)
        self.menu.addAction(open_gf_action)
        


        # Custom Presence (Only if game active)
        active_game = self.pm.forced_game or self.pm.last_game
        if active_game:
            gname = active_game.get("name", "Unknown")
            # Limit length
            if len(gname) > 25: gname = gname[:22] + "..."
            
            cp_action = QAction(f"Custom Presence: {gname}", self.menu)
            cp_action.triggered.connect(self.open_custom_presence_dialog)
            self.menu.addAction(cp_action)

        # Configuration Submenu
        config_menu = self.menu.addMenu(TEXTS.get("tray_config", "Configuration"))
        
        # 1. Start with Windows
        start_win_action = QAction(TEXTS.get("config_start_windows", "Start with Windows"), self.menu, checkable=True)
        start_win_action.setChecked(self.config_manager.get_setting("start_with_windows", False))
        start_win_action.triggered.connect(self.toggle_start_windows)
        config_menu.addAction(start_win_action)

        # 2. Start GeForce NOW
        start_gfn_action = QAction(TEXTS.get("config_start_gfn", "Start GeForce NOW on launch"), self.menu, checkable=True)
        start_gfn_action.setChecked(self.config_manager.get_setting("start_gfn_on_launch", False))
        start_gfn_action.triggered.connect(lambda chk: self.config_manager.set_setting("start_gfn_on_launch", chk))
        config_menu.addAction(start_gfn_action)

        # 3. Start Discord
        start_discord_action = QAction(TEXTS.get("config_start_discord", "Start Discord on launch"), self.menu, checkable=True)
        start_discord_action.setChecked(self.config_manager.get_setting("start_discord_on_launch", False))
        start_discord_action.triggered.connect(lambda chk: self.config_manager.set_setting("start_discord_on_launch", chk))
        config_menu.addAction(start_discord_action)

        # 4. Get cookie on launch
        start_cookie_action = QAction(TEXTS.get("config_get_cookie", "Get cookie on launch"), self.menu, checkable=True)
        start_cookie_action.setChecked(self.config_manager.get_setting("get_cookie_on_launch", True))
        start_cookie_action.triggered.connect(lambda chk: self.config_manager.set_setting("get_cookie_on_launch", chk))
        config_menu.addAction(start_cookie_action)

        self.menu.addSeparator()

        # Sync Games
        sync_text = TEXTS.get("tray_sync_games", "Sync games")
        sync_action = QAction(sync_text, self.menu)
        sync_action.triggered.connect(self.sync_games)
        self.menu.addAction(sync_action)
        
        # Open Logs
        logs_action = QAction(TEXTS.get("tray_open_logs", "Open logs"), self.menu)
        logs_action.triggered.connect(self.open_logs)
        self.menu.addAction(logs_action)

        # About
        about_action = QAction(TEXTS.get("about", "About"), self.menu)
        about_action.triggered.connect(self.open_about)
        self.menu.addAction(about_action)
        
        self.menu.addSeparator()
        
        # Exit
        exit_action = QAction(TEXTS.get("tray_exit", "Exit"), self.menu)
        exit_action.triggered.connect(QApplication.instance().quit)
        self.menu.addAction(exit_action)

    def update_menu(self):
        self.create_menu()

    def on_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.open_geforce()

    def toggle_start_windows(self, checked):
        self.config_manager.set_setting("start_with_windows", checked)
        set_autostart_windows(checked)

    def toggle_force_game(self):
        # 0. Check for running quests
        if getattr(self.pm, "active_quests", None):
            dlg = QuestListDialog(self.pm)
            dlg.set_add_game_callback(self.process_quest_input)
            dlg.exec_()
            return

        if self.pm.forced_game:
            self.pm.stop_force_game()
            self.showMessage("OK", "Forced game stopped.", QSystemTrayIcon.Information, 3000)
            self.update_menu()
            return
 
        dialog = AskGameDialog(title=TEXTS.get("force_game", "Force Game"), message=TEXTS.get("game_name", "Game Name:"))
        
        def on_quest_opened():
            dialog.reject()
            dlg = QuestListDialog(self.pm)
            dlg.set_add_game_callback(self.process_quest_input)
            dlg.exec_()
            
        def on_update_list_opened():
            self.showMessage("Info", "Updating Discord games list...", QSystemTrayIcon.Information, 4000)
            QApplication.processEvents()
            apps = self.pm._fetch_discord_apps_cached(force_download=True)
            if apps:
                self.showMessage("Info", f"Games list updated successfully ({len(apps)} apps).", QSystemTrayIcon.Information, 3000)
            else:
                self.showMessage("Error", "Could not update Discord games list.", QSystemTrayIcon.Warning, 4000)

        dialog.quest_mode_requested.connect(on_quest_opened)
        dialog.update_list_requested.connect(on_update_list_opened)

        if dialog.exec_() == QDialog.Accepted:
            game_name = dialog.get_game_name()
            if not game_name:
                return
            
            # Normal force game
            self.process_force_game(game_name)

    def process_quest_input(self, game_name):
        """
        Similar to process_force_game but for quests.
        Returns True if a game was successfully queued/started.
        """
        # Reuse search logic
        gm = self.pm.games_map or {}
        local_candidates = [k for k in gm if game_name.lower() in k.lower()]
        
        options = []
        if local_candidates:
            for k in local_candidates:
                score = 1.0 if k.lower() == game_name.lower() else 0.8
                options.append({"name": k, "id": gm[k].get("client_id"), "exe": gm[k].get("executable_path"), "score": score})
        
        discord_options = self.pm._find_discord_matches(game_name, max_candidates=50)
        for d_opt in discord_options:
            if not any(o["name"].lower() == d_opt["name"].lower() for o in options):
                options.append(d_opt)

        options.sort(key=lambda x: x.get("score", 0), reverse=True)
        options = options[:50]

        if not options:
            status = self.pm.check_discord_cache_status()
            if status["status"] == "MISSING" or status["hours"] > 168:
                self.showMessage("Searching...", f"Not found in cache (old/missing). Downloading recent data for '{game_name}'...", QSystemTrayIcon.Information, 4000)
                QApplication.processEvents() 
                apps = self.pm._fetch_discord_apps_cached(force_download=True)
                
                if apps:
                    discord_options2 = self.pm._find_discord_matches(game_name, max_candidates=50)
                    for d_opt in discord_options2:
                        if not any(o["name"].lower() == d_opt["name"].lower() for o in options):
                            options.append(d_opt)
                
                options.sort(key=lambda x: x.get("score", 0), reverse=True)
                options = options[:50]
        
        if not options:
            self.showMessage("Info", "No matches found.", QSystemTrayIcon.Information, 3000)
            return False
 
        # Show selection dialog
        sel_dialog = MatchSelectionDialog("Select Game (Quest)", options)
        if sel_dialog.exec_() == QDialog.Accepted and sel_dialog.selected_match:
            match = sel_dialog.selected_match
            self.apply_quest_game(match)
            return True
        return False

    def apply_quest_game(self, match):
        name = match["name"]
        exe = match.get("exe") or f"{name}.exe" # Fallback
        
        # Save cache
        self.pm._apply_discord_match(name, match)
        
        # Launch using PM
        self.pm.launch_quest_game(name, exe)

    def process_force_game(self, game_name):
        gm = self.pm.games_map or {}
        local_candidates = [k for k in gm if game_name.lower() in k.lower()]
        
        options = []
        if local_candidates:
            for k in local_candidates:
                score = 1.0 if k.lower() == game_name.lower() else 0.8
                options.append({"name": k, "id": gm[k].get("client_id"), "exe": gm[k].get("executable_path"), "score": score})
        
        # 1. Search in Discord (Local Cache First)
        discord_options = self.pm._find_discord_matches(game_name, max_candidates=50)
        for d_opt in discord_options:
            if not any(o["name"].lower() == d_opt["name"].lower() for o in options):
                options.append(d_opt)

        options.sort(key=lambda x: x.get("score", 0), reverse=True)
        options = options[:50]

        # 2. If no matches, force download and search again
        if not options:
            status = self.pm.check_discord_cache_status()
            if status["status"] == "MISSING" or status["hours"] > 168:
                self.showMessage("Searching...", f"Not found in cache (old/missing). Downloading recent Discord data for '{game_name}'...", QSystemTrayIcon.Information, 4000)
                QApplication.processEvents() # Keep UI responsive (mostly)
                
                # Update cache
                apps = self.pm._fetch_discord_apps_cached(force_download=True)
                
                # Search again
                if apps:
                    discord_options2 = self.pm._find_discord_matches(game_name, max_candidates=50)
                    for d_opt in discord_options2:
                        if not any(o["name"].lower() == d_opt["name"].lower() for o in options):
                            options.append(d_opt)
                
                options.sort(key=lambda x: x.get("score", 0), reverse=True)
                options = options[:50]

        # Note: We don't apply automatically here loop; we show selection dialog

        if not options:
            self.showMessage("Info", "No matches found in JSON or Discord (even after update).", QSystemTrayIcon.Information, 3000)
            return

        # Show selection dialog
        sel_dialog = MatchSelectionDialog("Select Game", options)
        if sel_dialog.exec_() == QDialog.Accepted and sel_dialog.selected_match:
            match = sel_dialog.selected_match
            self.apply_force_game(match)

    def apply_force_game(self, match):
        name = match["name"]
        cid = match.get("id")
        exe = match.get("exe")
        
        # PERSISTENCE: Save the match to games_config_merged.json
        # This ensures next time we have it in games_map and don't need to search/download
        self.pm._apply_discord_match(name, match)
        
        if cid:
            try:
                def reconnect_after_delay():
                    time.sleep(11)
                
                self.pm._disconnect_rpc_temporarily()
                
                self.pm.client_id = cid
                self.pm._connect_rpc(cid)
                logger.info(f"🔁 RPC reconnected with forced client_id: {cid}")
            except Exception as e:
                logger.error(f"❌ Error reconnecting RPC after forcing game: {e}")
                threading.Thread(target=reconnect_after_delay, daemon=True).start()

        if exe:
            try:
                self.pm.close_fake_executable()
            except Exception as e:
                logger.debug(f"Could not close previous executable: {e}")
            self.pm.launch_fake_executable(exe)

        self.pm.forced_game = {
            "name": name,
            "client_id": cid,
            "executable_path": exe
        }
        self.pm.last_game = dict(self.pm.forced_game)
        logger.info(f"🎮 Forced game activated: {name} (id={cid})")
        
        self.showMessage("OK", f"{TEXTS.get('tray_forced_game', 'Forced game')}: {name}", QSystemTrayIcon.Information, 3000)
        self.update_menu()

    def obtain_cookie(self):
        def confirm_callback(title, message):
            return GamingMessageBox.show_question(None, title, message)

        cookie = self.pm.cookie_manager.ask_and_obtain_cookie(confirm_callback)
        if cookie:
            self.pm.update_cookie(cookie)
            self.showMessage(TEXTS.get("cookie_title", "Cookie"), TEXTS.get("cookie_saved", "Cookie saved"), QSystemTrayIcon.Information, 3000)
        else:
            self.showMessage(TEXTS.get("cookie_title", "Cookie"), TEXTS.get("cookie_invalid", "Cookie invalid"), QSystemTrayIcon.Warning, 3000)

    def open_geforce(self):
        AppLauncher.launch_geforce_now()

    def open_logs(self):
        if LOG_FILE.exists():
            try:
                if IS_WINDOWS:
                    os.startfile(LOG_FILE)
                elif IS_LINUX:
                    subprocess.Popen(['xdg-open', str(LOG_FILE)])
                elif IS_MACOS:
                    subprocess.Popen(['open', str(LOG_FILE)])
            except Exception as e:
                logger.error(f"Could not open log file: {e}")
                self.showMessage(TEXTS.get("logs_title", "Logs"), f"Log: {LOG_FILE}", QSystemTrayIcon.Information, 5000)
        else:
            self.showMessage(TEXTS.get("logs_title", "Logs"), TEXTS.get("open_logs_error", "No log file found."), QSystemTrayIcon.Warning, 3000)

    def open_about(self):
        dlg = AboutDialog()
        dlg.exec_()

    def open_custom_presence_dialog(self):
        game = self.pm.forced_game or self.pm.last_game
        if not game:
            self.showMessage("Error", "No active game.", QSystemTrayIcon.Warning)
            return
            
        name = game.get("name", "Unknown")
        # Pass current custom values if any
        dlg = CustomPresenceDialog(name, game, parent=None)
        if dlg.exec_() == QDialog.Accepted and dlg.result_data:
            self.pm.set_custom_presence(dlg.result_data)
            self.showMessage("Custom Presence", f"Presence updated for {name}", QSystemTrayIcon.Information, 2000)

    def on_match_selection_requested(self, game_key, candidates):
        # This is called from PresenceManager when it finds a new game and needs user input
        # We need to run this in the main thread (which signals do automatically)
        dialog = MatchSelectionDialog(game_key, candidates)
        if dialog.exec_() == QDialog.Accepted:
            self.pm.on_match_selected(game_key, dialog.selected_match)
        else:
            self.pm.on_match_selected(game_key, None)

    def on_download_progress(self, current, total):
        if current == -1 and total == -1:
            if getattr(self, '_download_progress_dlg', None):
                self._download_progress_dlg.close()
                self._download_progress_dlg.deleteLater()
                self._download_progress_dlg = None
            return
 
        if not getattr(self, '_download_progress_dlg', None):
            self._download_progress_dlg = QProgressDialog("Downloading games list...", "Cancel", 0, total if total > 0 else 0, None)
            self._download_progress_dlg.setStyleSheet(GAMING_STYLESHEET)
            self._download_progress_dlg.setWindowModality(Qt.WindowModal)
            self._download_progress_dlg.setMinimumDuration(1500) # Solo mostrar si la descarga toma mas de 1.5s
            self._download_progress_dlg.setAutoReset(False)
            self._download_progress_dlg.setAutoClose(False)
            # No forzamos show() para evitar ventanas blancas parpadeantes en descargas rípidas
            
        if getattr(self, '_download_progress_dlg', None):
            if total > 0:
                self._download_progress_dlg.setMaximum(total)
            self._download_progress_dlg.setValue(current)
            
            def fmt(sz):
                if sz < 1024 * 1024:
                    return f"{sz / 1024:.1f} KB"
                return f"{sz / 1024 / 1024:.2f} MB"
                
            msg = f"Downloading games list... ({fmt(current)} / {fmt(total)})" if total > 0 else f"Downloading games list... ({fmt(current)})"
            self._download_progress_dlg.setLabelText(msg)
            QApplication.processEvents()
            
            if self._download_progress_dlg and self._download_progress_dlg.wasCanceled():
                self._download_progress_dlg.close()
                self._download_progress_dlg.deleteLater()
                self._download_progress_dlg = None

    def sync_games(self):
        status = self.pm.check_discord_cache_status()
        force = False
        
        if status["status"] == "FRESH":
            hours = status["hours"]
            msg = f"The cache file was updated {hours:.1f} hours ago.\nDo you want to update it again?"
            if GamingMessageBox.show_question(None, "Sync Games", msg):
                force = True
            # If No, we proceed with force=False (just local matching)
        
        # Create Progress Dialog
        self.progress = QProgressDialog("Syncing games...", "Cancel", 0, 100, None)
        self.progress.setStyleSheet(GAMING_STYLESHEET)
        self.progress.setWindowModality(Qt.WindowModal)
        self.progress.setMinimumDuration(0)
        self.progress.setValue(0)
        self.progress.canceled.connect(self.on_sync_canceled)
        self.progress.show()
        
        # Connect signals
        try:
            self.pm.sync_progress.disconnect()
            self.pm.sync_finished.disconnect()
            self.pm.sync_error.disconnect()
        except:
            pass

        self.pm.sync_progress.connect(self.on_sync_progress)
        self.pm.sync_finished.connect(self.on_sync_finished)
        self.pm.sync_error.connect(self.on_sync_error)
        
        # Start thread
        threading.Thread(target=self.pm.sync_missing_game_details, args=(force,), daemon=True).start()

    def on_sync_canceled(self):
        logger.info("Requesting sync cancellation...")
        self.pm.cancel_sync()

    def on_sync_progress(self, current, total, updated, eta_str):
        if getattr(self, 'progress', None):
            self.progress.setMaximum(total)
            self.progress.setValue(current)
            self.progress.setLabelText(f"Syncing games...\nChecked: {current}/{total} - New/Updated: {updated}\nRemaining time: {eta_str}")

    def on_sync_finished(self, updated, total):
        if getattr(self, 'progress', None):
            self.progress.close()
            self.progress = None
        
        GamingMessageBox.show_info(None, "Sync Completed", f"Successfully updated {updated} games out of {total} processed.")
        
    def on_sync_error(self, error_msg):
        if getattr(self, 'progress', None):
            self.progress.close()
            self.progress = None
        GamingMessageBox.show_warning(None, "Sync Error", f"An error occurred: {error_msg}")

    def on_gfn_error_detected(self):
        if self._reinstaller_worker and self._reinstaller_worker.isRunning():
            return
        
        # We create and show the dialog non-modally or modally
        if self._repair_dialog is None:
            self._repair_dialog = GFNRepairDialog()
            
        self._repair_dialog.show()
        
        self._reinstaller_worker = GFNReinstallerWorker()
        
        # Connect signals
        self._reinstaller_worker.started_reinstall.connect(self.on_reinstall_started)
        self._reinstaller_worker.progress_update.connect(self._repair_dialog.on_progress)
        self._reinstaller_worker.status_update.connect(self._repair_dialog.on_status)
        self._reinstaller_worker.error_occurred.connect(self._repair_dialog.on_error)
        self._reinstaller_worker.error_occurred.connect(self.on_reinstall_error)
        self._reinstaller_worker.finished_reinstall.connect(self._repair_dialog.on_finished)
        self._reinstaller_worker.finished_reinstall.connect(self.on_reinstall_finished)
        
        self._reinstaller_worker.start()

    def on_reinstall_started(self):
        self.showMessage("GeForce NOW Error", "Corrupt resource detected. Repairing and installing GFN...", QSystemTrayIcon.Information, 5000)

    def on_reinstall_finished(self):
        self.showMessage("GeForce NOW Repaired", "GeForce NOW has been successfully reinstalled.", QSystemTrayIcon.Information, 5000)
        AppLauncher.launch_geforce_now()

    def on_reinstall_error(self, err):
        self.showMessage("Repair Error", f"Could not reinstall GFN: {err}", QSystemTrayIcon.Warning, 5000)
