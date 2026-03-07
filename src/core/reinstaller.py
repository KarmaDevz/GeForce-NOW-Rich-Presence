import os
import time
import psutil
import requests
import subprocess
import tempfile
import logging
import shutil
import platform
from pathlib import Path
from PyQt5.QtCore import QThread, pyqtSignal

IS_WINDOWS = platform.system() == "Windows"

class GFNReinstallerWorker(QThread):
    started_reinstall = pyqtSignal()
    finished_reinstall = pyqtSignal()
    error_occurred = pyqtSignal(str)
    
    # New signals for the progress dialog
    progress_update = pyqtSignal(int)
    status_update = pyqtSignal(str)

    def run(self):
        logger = logging.getLogger('geforce_presence')
        if not IS_WINDOWS:
            logger.info("GFN repair skipped (Windows only feature).")
            self.error_occurred.emit("repair_windows_only")
            return
        try:
            self.started_reinstall.emit()
            self.progress_update.emit(0)
            self.status_update.emit("repair_status_init")
            logger.info("🛠️ Inciando reparación completa de GeForce NOW...")
            
            # 1. Kill GFN processes
            self.status_update.emit("repair_status_kill")
            self.progress_update.emit(10)
            logger.info("🔪 Cerrando procesos de GeForce NOW...")
            for proc in psutil.process_iter(attrs=['name']):
                name = (proc.info.get('name') or "").lower()
                if "geforcenow" in name:
                    try:
                        proc.kill()
                    except Exception:
                        pass
            
            time.sleep(2)  # Wait for release
            
            # 2. Clean corrupted files (Uninstall)
            self.status_update.emit("repair_status_uninstall")
            self.progress_update.emit(25)
            logger.info("🗑️ Eliminando archivos locales (Cef/AppData)...")
            local_appdata = os.getenv("LOCALAPPDATA", "")
            if local_appdata:
                gfn_dir = Path(local_appdata) / "NVIDIA Corporation" / "GeForceNOW"
                if gfn_dir.exists():
                    try:
                        shutil.rmtree(gfn_dir, ignore_errors=True)
                        logger.info("✅ Archivos de GeForce NOW eliminados.")
                    except Exception as e:
                        logger.warning(f"⚠️ No se pudo eliminar completamente la carpeta: {e}")
            
            # 3. Download installer
            self.status_update.emit("repair_status_download")
            self.progress_update.emit(40)
            url = "https://download.nvidia.com/gfnpc/GeForceNOW-release.exe"
            installer_path = os.path.join(tempfile.gettempdir(), "GeForceNOW-release.exe")
            
            logger.info("⬇️ Descargando instalador de GFN...")
            response = requests.get(url, stream=True, timeout=60)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(installer_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        # Map download to 40% -> 80% progress
                        percent = int(40 + (downloaded / total_size) * 40)
                        self.progress_update.emit(percent)
                    
            logger.info("✅ Instalador descargado. Ejecutando instalación silenciosa...")
            
            # 4. Run installer silently
            self.status_update.emit("repair_status_install")
            self.progress_update.emit(85)
            
            # subprocess.run blocks, so we update UI just before
            result = subprocess.run([installer_path, "-s"], capture_output=True, text=True)
            
            if result.returncode == 0:
                self.progress_update.emit(100)
                self.status_update.emit("repair_status_done")
                logger.info("✅ Reinstalación completada con éxito.")
                self.finished_reinstall.emit()
            else:
                logger.error(f"❌ Error en la instalación: {result.stderr}")
                self.error_occurred.emit(f"Installer returned code {result.returncode}")
                
            # Cleanup installer file
            try:
                os.remove(installer_path)
            except Exception:
                pass

        except Exception as e:
            logger.error(f"❌ Error durante reinstalación silenciosa: {e}")
            self.error_occurred.emit(str(e))

