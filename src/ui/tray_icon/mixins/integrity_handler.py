import os
import logging
from typing import TYPE_CHECKING

from PyQt5.QtWidgets import QSystemTrayIcon, QProgressDialog, QApplication
from PyQt5.QtCore import Qt

from src.core.utils import (get_lang_from_registry, load_locale, CONFIG_DIR, 
                            validate_games_config, safe_json_load, save_json, 
                            download_from_github)
from src.core.reinstaller import GFNReinstallerWorker
from src.core.app_launcher import AppLauncher
from src.ui.dialogs import GAMING_STYLESHEET, GamingMessageBox
from ..dialogs import GFNRepairDialog

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

class IntegrityHandlerMixin(Base):
    def verify_integrity(self):
        # 1. Verify Configuration Files
        config_ok = True
        fixed_path = CONFIG_DIR / "games_config_merged.json"
        
        data = None
        if fixed_path.exists():
            data = safe_json_load(fixed_path)
            if not validate_games_config(data):
                config_ok = False
        else:
            config_ok = False
            
        if not config_ok:
            logger.info("Verificar Integridad: games_config_merged.json no existe o está corrupto. Descargando de GitHub...")
            data = download_from_github("games_config_merged.json")
            if validate_games_config(data):
                save_json(data, fixed_path)
                self.pm.games_map = data
                logger.info("✅ games_config_merged.json restaurado y recargado con éxito.")
                self.showMessage(
                    self.texts.get("integrity_title", "Verificar Integridad"), 
                    "Archivo de configuración restaurado de GitHub correctamente.", 
                    QSystemTrayIcon.Information, 
                    3000
                )
            else:
                logger.error("❌ No se pudo descargar el archivo de configuración desde GitHub.")
                GamingMessageBox.show_warning(
                    None,
                    "Error de Integridad",
                    "El archivo de configuración local está corrupto y no se pudo descargar el respaldo desde GitHub. Por favor comprueba tu conexión a internet."
                )
                return
        
        # 2. Validate GeForce NOW
        # Show a progress/status dialog to let the user know we are verifying GeForce NOW
        progress = QProgressDialog(
            self.texts.get("verifying_gfn", "Verificando integridad de GeForce NOW..."), 
            None, 
            0, 
            100, 
            None
        )
        progress.setWindowTitle(self.texts.get("integrity_title", "Verificar Integridad"))
        progress.setStyleSheet(GAMING_STYLESHEET)
        progress.setWindowModality(Qt.ApplicationModal)
        progress.setAutoClose(True)
        progress.setValue(10)
        QApplication.processEvents()
        
        # If GFN is not running, launch it to check if it corrupts on launch
        from src.core.app_launcher import AppLauncher
        import sys
        import psutil
        import subprocess
        
        target_proc = "GeForceNOW.exe" if sys.platform == "win32" else "GeForceNOW"
        is_running = AppLauncher._is_process_running_by_name(target_proc)
        if sys.platform == "darwin" and not is_running:
            is_running = AppLauncher._is_process_running_by_name("GeForce NOW")
            
        if not is_running:
            logger.info("Verificar Integridad: GeForce NOW no está ejecutándose. Iniciando para validar...")
            AppLauncher.launch_geforce_now()
            
        # We will wait up to 8 seconds, checking visible window titles of the GFN process for corruption
        corrupted = False
        import time
        start_time = time.time()
        
        # We loop and sleep, letting GUI update
        while time.time() - start_time < 8.0:
            # Update progress value gradually
            val = int(10 + (time.time() - start_time) * 10)
            progress.setValue(min(val, 95))
            QApplication.processEvents()
            
            # Look for GFN processes
            gef_pids = set()
            try:
                for proc in psutil.process_iter(['name', 'pid']):
                    pname = (proc.info.get('name') or "").lower()
                    if "geforcenow" in pname or "geforce now" in pname:
                        gef_pids.add(proc.pid)
            except Exception:
                pass
                
            if gef_pids:
                if sys.platform == "win32":
                    import win32gui
                    import win32process
                    
                    hwnds = []
                    win32gui.EnumWindows(lambda h, p: p.append(h) if win32gui.IsWindowVisible(h) else None, hwnds)
                    for hwnd in hwnds:
                        try:
                            _, pid = win32process.GetWindowThreadProcessId(hwnd)
                            if pid in gef_pids:
                                title = win32gui.GetWindowText(hwnd)
                                if "Application Launch failed" in title or "Application resource corrupted" in title:
                                    corrupted = True
                                    logger.warning(f"Corrupción de GFN detectada en ventana: {title}")
                                    break
                        except Exception:
                            continue
                elif sys.platform == "darwin":
                    cmd = """
                    tell application "System Events"
                        set geforceProcesses to every process whose name contains "GeForce"
                        repeat with proc in geforceProcesses
                            try
                                set windowNames to name of every window of proc
                                if count of windowNames > 0 then
                                    return item 1 of windowNames
                                end if
                            end try
                        end repeat
                    end tell
                    return ""
                    """
                    result = subprocess.run(["osascript", "-e", cmd], capture_output=True, text=True)
                    if result.returncode == 0:
                        title = result.stdout.strip()
                        if "Application Launch failed" in title or "Application resource corrupted" in title:
                            corrupted = True
                            break
                            
            if corrupted:
                break
                
            time.sleep(0.3)
            
        progress.close()
        
        # If GFN is corrupted, trigger repair!
        if corrupted:
            logger.warning("Verificar Integridad: GeForce NOW corrupto detectado. Iniciando reparación...")
            self.on_gfn_error_detected()
        else:
            # Everything is OK!
            logger.info("Verificar Integridad: GeForce NOW se inició sin corrupción.")
            
            # Show a success message
            GamingMessageBox.show_info(
                None, 
                self.texts.get("integrity_title", "Verificar Integridad"), 
                self.texts.get("integrity_ok_msg", "Todos los archivos de configuración e instalaciones están en perfecto estado.")
            )

    def on_download_progress(self, current, total):
        if current == -1 and total == -1:
            if getattr(self, '_download_progress_dlg', None):
                self._download_progress_dlg.close()
                self._download_progress_dlg.deleteLater()
                self._download_progress_dlg = None
            self._download_cancelled = False
            return

        if getattr(self, '_download_cancelled', False):
            return

        if not getattr(self, '_download_progress_dlg', None):
            self._download_progress_dlg = QProgressDialog("Descargando lista de juegos...", "Cancelar", 0, total if total > 0 else 0, None)
            self._download_progress_dlg.setStyleSheet(GAMING_STYLESHEET)
            self._download_progress_dlg.setWindowModality(Qt.WindowModal)
            self._download_progress_dlg.setMinimumDuration(1500)
            self._download_progress_dlg.setAutoReset(False)
            self._download_progress_dlg.setAutoClose(False)
            
        if getattr(self, '_download_progress_dlg', None):
            if total > 0:
                self._download_progress_dlg.setMaximum(total)
            self._download_progress_dlg.setValue(current)
            
            def fmt(sz):
                if sz < 1024 * 1024:
                    return f"{sz / 1024:.1f} KB"
                return f"{sz / 1024 / 1024:.2f} MB"
                
            msg = f"Descargando lista de juegos... ({fmt(current)} / {fmt(total)})" if total > 0 else f"Descargando lista de juegos... ({fmt(current)})"
            self._download_progress_dlg.setLabelText(msg)
            QApplication.processEvents()
            
            if self._download_progress_dlg and self._download_progress_dlg.wasCanceled():
                self._download_progress_dlg.close()
                self._download_progress_dlg.deleteLater()
                self._download_progress_dlg = None
                self._download_cancelled = True

    def on_gfn_error_detected(self):
        if self._reinstaller_worker and self._reinstaller_worker.isRunning():
            return
        
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
        self.showMessage("GeForce NOW Error", "Recurso corrupto detectado. Reparando e instalando GFN...", QSystemTrayIcon.Information, 5000)

    def on_reinstall_finished(self):
        self.showMessage("GeForce NOW Reparado", "GeForce NOW se ha reinstalado correctamente.", QSystemTrayIcon.Information, 5000)
        AppLauncher.launch_geforce_now()

    def on_reinstall_error(self, err):
        self.showMessage("Error de Reparación", f"No se pudo reinstalar GFN: {err}", QSystemTrayIcon.Warning, 5000)
