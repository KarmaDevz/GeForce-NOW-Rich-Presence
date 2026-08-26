import sys
import os
import json
import hashlib
import logging
import requests
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Tuple, Union

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton, QProgressBar, QHBoxLayout,
    QScrollArea
)
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QObject
from PyQt5.QtGui import QIcon

from src.version import VERSION
from src.utils.i18n import t
from src.core.utils import ASSETS_DIR

# Common Stylesheet to match the rest of the app (Copied from dialogs.py to avoid circular imports)
GAMING_STYLESHEET = """
    QDialog {
        background-color: #0d0e10;
        border: 2px solid #1b1f23;
        border-radius: 14px;
    }

    QLabel {
        font-size: 14px;
        font-family: "TT Octosquares Trl Cnd";
        color: #e0e0e0;
        padding-bottom: 4px;
    }
    
    QLabel#title_label {
        font-size: 18px;
        font-weight: bold;
        color: #ffffff;
        padding-bottom: 8px;
    }

    QLineEdit, QSpinBox {
        padding: 8px;
        font-size: 14px;
        border: 1px solid #2c2f33;
        border-radius: 6px;
        background: #1a1b1d;
        color: #ffffff;
        font-family: "TT Octosquares Trl Cnd";
        font-weight: bold;
    }

    QLineEdit:focus, QSpinBox:focus {
        border: 2px solid #454C55;
    }

    QPushButton {
        background-color: #045D0E;
        color: #FFFFFF;
        padding: 8px 16px;
        border-radius: 6px;
        font-size: 14px;
        font-family: "TT Octosquares Trl Cnd";
        font-weight: bold;
    }

    QPushButton:hover {
        background-color: #12881F;
    }
    
    QPushButton:pressed {
        background-color: #03420a;
    }

    QPushButton#secondary {
        background-color: #2c2f33;
        color: #e6e6e6;
    }

    QPushButton#secondary:hover {
        background-color: #3c3f43;
    }

    /* LIST WIDGET & SCROLLBARS */
    QListWidget {
        background: #131416;
        border: 1px solid #1f2428;
        border-radius: 8px;
        padding: 6px;
        font-size: 13px;
        font-family: Consolas, monospace;
        color: #cfcfcf;
    }

    QListWidget::item {
        padding: 8px;
        border-radius: 4px;
        color: #dfdfdf;
    }

    QListWidget::item:selected {
        background-color: #00e676;
        color: #0e0f11;
        font-weight: bold;
    }

    QScrollBar:vertical {
        background: transparent;
        width: 8px;
        margin: 4px 0;
    }
    QScrollBar::handle:vertical {
        background: #383a3d;
        border-radius: 4px;
        min-height: 30px;
    }
    QScrollBar::handle:vertical:hover {
        background: #4a4d50;
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0; 
        background: none; 
    }
"""

logger = logging.getLogger('geforce_presence')
GITHUB_RELEASES_URL = "https://api.github.com/repos/KarmaDevz/GeForce-NOW-Rich-Presence/releases/latest"

def get_current_lang():
    try:
        from src.core.utils import get_lang_from_registry
        return get_lang_from_registry()
    except Exception:
        return os.getenv('GEFORCE_LANG', 'en')

def filter_release_notes(body: str, lang: str) -> str:
    if not body:
        return ""
    
    import re
    tags = re.findall(r'\[([a-zA-Z]{2})\]', body)
    if not tags:
        return body
        
    lang_upper = lang.upper()
    tags_upper = [t.upper() for t in tags]
    
    if lang_upper in tags_upper:
        target_tag = lang_upper
    elif 'EN' in tags_upper:
        target_tag = 'EN'
    else:
        target_tag = tags[0].upper()
        
    pattern = r'\[[a-zA-Z]{2}\]'
    parts = re.split(pattern, body)
    
    for i, tag in enumerate(tags):
        if tag.upper() == target_tag:
            return parts[i+1].strip()
            
    return body

def parse_version(v_str: str) -> Tuple[int, ...]:
    """Simple semantic version parser ('v1.0.0' -> (1, 0, 0))"""
    try:
        return tuple(map(int, v_str.lstrip('v').split('.')))
    except Exception:
        return (0, 0, 0)

def get_file_sha256(filepath: Union[str, Path]) -> str:
    """Calculates the SHA-256 hash of a file."""
    hasher = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest().lower()

def parse_sha256sums(content_str: str) -> Dict[str, str]:
    """
    Parses SHA256SUMS.txt format into a dict mapping exact filename to sha256 lowercase hash.
    Supports standard GNU formats:
      <hash>  <filename>
      <hash> *<filename>
    Handles multiple whitespace/tabs, comments (#), and blank lines.
    """
    checksums: Dict[str, str] = {}
    if not content_str:
        return checksums
    for line in content_str.strip().splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        parts = line.split(None, 1)
        if len(parts) == 2:
            hash_val = parts[0].strip().lower()
            filename = parts[1].strip()
            if filename.startswith('*'):
                filename = filename[1:].strip()
            if len(hash_val) == 64:
                checksums[filename] = hash_val
    return checksums

def get_installed_build(file_path: Optional[Union[str, Path]] = None) -> Optional[dict]:
    """
    Safely reads installed_build.json.
    Returns the parsed dictionary or None if missing/corrupt.
    """
    try:
        if file_path is None:
            from src.core.utils import USER_DATA_DIR
            file_path = USER_DATA_DIR / "installed_build.json"
        
        path_obj = Path(file_path)
        if not path_obj.exists() or not path_obj.is_file():
            return None
            
        with open(path_obj, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict) and "version" in data:
                return data
    except Exception as e:
        logger.warning(f"Error al leer installed_build.json: {e}")
    return None

def save_installed_build(build_info: dict, file_path: Optional[Union[str, Path]] = None) -> bool:
    """
    Atomically saves build_info to installed_build.json using a temp file and os.replace().
    """
    temp_file = None
    try:
        if file_path is None:
            from src.core.utils import USER_DATA_DIR
            file_path = USER_DATA_DIR / "installed_build.json"
            
        path_obj = Path(file_path)
        path_obj.parent.mkdir(parents=True, exist_ok=True)
        
        temp_file = path_obj.parent / f"{path_obj.name}.tmp.{os.getpid()}"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(build_info, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
            
        os.replace(str(temp_file), str(path_obj))
        logger.info(f"💾 installed_build.json guardado correctamente: v{build_info.get('version')} (SHA: {build_info.get('sha256', '')[:8]}...)")
        return True
    except Exception as e:
        logger.error(f"Error al guardar installed_build.json: {e}")
        if temp_file and temp_file.exists():
            try:
                temp_file.unlink()
            except Exception:
                pass
        return False

def get_platform_asset(release_data: dict) -> Optional[dict]:
    """
    Finds the exact asset dictionary matching the current operating system.
    """
    from src.core.utils import IS_WINDOWS, IS_MACOS, IS_LINUX
    assets = release_data.get("assets", [])
    
    # 1. Look for platform specific zip / tar.gz for silent updates
    for asset in assets:
        name_lower = asset.get("name", "").lower()
        if IS_WINDOWS and name_lower.endswith(".zip") and "windows" in name_lower:
            return asset
        elif IS_MACOS and name_lower.endswith(".zip") and "macos" in name_lower:
            return asset
        elif IS_LINUX and name_lower.endswith(".tar.gz") and "linux" in name_lower:
            return asset

    # 2. Fallback to Windows .exe installer if on Windows
    if IS_WINDOWS:
        for asset in assets:
            if asset.get("name", "").lower().endswith(".exe"):
                return asset

    return None

def get_remote_checksum(release_data: dict, asset_name: str) -> Optional[str]:
    """
    Looks for SHA256SUMS.txt in release assets and retrieves the exact SHA-256 for asset_name.
    """
    if not asset_name:
        return None
    assets = release_data.get("assets", [])
    checksum_url = None
    for asset in assets:
        if asset.get("name") in ("SHA256SUMS.txt", "checksums.txt", "SHA256SUMS"):
            checksum_url = asset.get("browser_download_url")
            break
            
    if not checksum_url:
        return None
        
    try:
        resp = requests.get(checksum_url, timeout=10)
        if resp.status_code == 200:
            parsed = parse_sha256sums(resp.text)
            return parsed.get(asset_name)
    except Exception as e:
        logger.warning(f"No se pudo obtener SHA256SUMS.txt del release: {e}")
    return None

def is_build_newer_or_different(
    current_version_str: str,
    installed_build: Optional[dict],
    release_data: dict,
    platform_asset: dict,
    remote_sha256: Optional[str]
) -> Tuple[bool, str]:
    """
    Determines if an update should be performed based on:
    1. Semantic versioning (latest > current -> newer_version).
    2. SHA-256 checksum (Source of Truth) for identical version numbers.
    3. Asset metadata fallback (id, updated_at) if SHA256SUMS.txt is absent.
    
    Returns (should_update: bool, reason: str).
    """
    latest_version_str = release_data.get("tag_name", "v0.0.0")
    latest_ver = parse_version(latest_version_str)
    current_ver = parse_version(current_version_str)
    
    if latest_ver > current_ver:
        return (True, "newer_version")
    elif latest_ver < current_ver:
        return (False, "older_version")
        
    # Same version number: Check for hotfix / recompilation
    # Priority 1: SHA-256 Checksum (Source of Truth)
    if remote_sha256:
        if installed_build and installed_build.get("sha256"):
            local_sha = installed_build.get("sha256", "").lower()
            if local_sha and local_sha != remote_sha256.lower():
                logger.info(f"🔥 Hotfix/Recompilación detectada para {latest_version_str} vía SHA-256 (Local: {local_sha[:8]}..., Remoto: {remote_sha256[:8]}...)")
                return (True, "hotfix_hash_mismatch")
            else:
                logger.info(f"✅ Versión {latest_version_str} ya instalada con el mismo SHA-256.")
                return (False, "same_build")
        else:
            # Baseline for existing installs with identical version number
            logger.info(f"ℹ️ Versión {latest_version_str} coincide sin installed_build.json previo. Estableciendo línea base.")
            return (False, "same_build_baseline_needed")
            
    # Priority 2: Metadata Fallback (if SHA256SUMS.txt was not available)
    if installed_build:
        saved_name = installed_build.get("asset_name")
        current_name = platform_asset.get("name")
        
        if saved_name == current_name:
            saved_id = installed_build.get("asset_id")
            current_id = platform_asset.get("id")
            saved_updated_at = installed_build.get("updated_at")
            current_updated_at = platform_asset.get("updated_at")
            
            if (saved_id and current_id and saved_id != current_id) or \
               (saved_updated_at and current_updated_at and saved_updated_at != current_updated_at):
                logger.info(f"🔥 Hotfix/Recompilación detectada para {latest_version_str} vía metadatos de GitHub (ID: {saved_id}->{current_id}, Fecha: {saved_updated_at}->{current_updated_at})")
                return (True, "metadata_changed")

    return (False, "same_build")

def verify_downloaded_checksum(file_path: Union[str, Path], expected_sha256: Optional[str]) -> bool:
    """Verifies downloaded file against expected SHA-256."""
    if not expected_sha256:
        return True
    actual_sha = get_file_sha256(file_path)
    is_valid = (actual_sha.lower() == expected_sha256.lower())
    if not is_valid:
        logger.error(f"❌ Error de verificación de Checksum! Esperado: {expected_sha256.lower()}, Obtenido: {actual_sha.lower()}")
    else:
        logger.info(f"✅ Checksum SHA-256 verificado exitosamente ({actual_sha[:8]}...)")
    return is_valid


class UpdateWorker(QThread):
    check_finished = pyqtSignal(bool, str, str, str, dict, str) # has_update, version, url, release_notes, target_metadata, update_reason
    download_progress = pyqtSignal(int)
    download_finished = pyqtSignal(str) # path to installer
    error_occurred = pyqtSignal(str)

    def __init__(self, mode="check", download_url=None, target_metadata=None):
        super().__init__()
        self.mode = mode
        self.download_url = download_url
        self.target_metadata = target_metadata or {}

    def run(self):
        if self.mode == "check":
            self.check_updates()
        elif self.mode == "download":
            self.download_update()

    def check_updates(self):
        try:
            logger.info("📦 Buscando actualizaciones...")
            response = requests.get(GITHUB_RELEASES_URL, timeout=10)
            response.raise_for_status()
            data = response.json()

            latest_version_str = data.get("tag_name", "v0.0.0")
            logger.info(f"📦 Versión actual: {VERSION}, Última versión GitHub: {latest_version_str}")

            platform_asset = get_platform_asset(data)
            if not platform_asset:
                logger.warning("No se encontró un archivo de actualización compatible para la plataforma.")
                self.check_finished.emit(False, "", "", "", {}, "no_asset")
                return

            asset_name = platform_asset.get("name", "")
            update_url = platform_asset.get("browser_download_url", "")
            remote_sha256 = get_remote_checksum(data, asset_name)
            installed_build = get_installed_build()

            should_update, reason = is_build_newer_or_different(
                current_version_str=VERSION,
                installed_build=installed_build,
                release_data=data,
                platform_asset=platform_asset,
                remote_sha256=remote_sha256
            )

            # Establish baseline if user is on identical version and has no previous build record
            if reason == "same_build_baseline_needed" and not installed_build:
                baseline_info = {
                    "version": VERSION.lstrip('v'),
                    "asset_name": asset_name,
                    "asset_id": platform_asset.get("id"),
                    "sha256": remote_sha256 or "",
                    "size": platform_asset.get("size", 0),
                    "updated_at": platform_asset.get("updated_at", ""),
                    "installed_at": datetime.now(timezone.utc).isoformat()
                }
                save_installed_build(baseline_info)

            if should_update:
                target_metadata = {
                    "version": latest_version_str.lstrip('v'),
                    "asset_name": asset_name,
                    "asset_id": platform_asset.get("id"),
                    "sha256": remote_sha256 or "",
                    "size": platform_asset.get("size", 0),
                    "updated_at": platform_asset.get("updated_at", "")
                }
                self.check_finished.emit(True, latest_version_str, update_url, data.get("body", ""), target_metadata, reason)
            else:
                self.check_finished.emit(False, "", "", "", {}, reason)

        except Exception as e:
            logger.error(f"Error al buscar actualizaciones: {e}")
            self.error_occurred.emit(str(e))

    def download_update(self):
        try:
            logger.info(f"Descargando actualización desde {self.download_url}")
            response = requests.get(self.download_url, stream=True, timeout=30)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0
            
            tmp_dir = Path(tempfile.gettempdir()) / "geforce_update"
            tmp_dir.mkdir(parents=True, exist_ok=True)
            
            url_lower = self.download_url.lower()
            if url_lower.endswith(".zip"):
                ext = ".zip"
            elif url_lower.endswith(".tar.gz"):
                ext = ".tar.gz"
            else:
                ext = ".exe"
                
            installer_path = tmp_dir / f"update{ext}"

            with open(installer_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        if total_size > 0:
                            progress = int((downloaded_size / total_size) * 100)
                            self.download_progress.emit(progress)

            # Pre-installation Verification: Check SHA-256 before allowing install
            expected_sha = (self.target_metadata or {}).get("sha256")
            if expected_sha:
                if not verify_downloaded_checksum(installer_path, expected_sha):
                    try:
                        if installer_path.exists():
                            installer_path.unlink()
                    except Exception:
                        pass
                    raise ValueError("El checksum SHA-256 del archivo descargado no coincide con el publicado en el Release.")
            else:
                # If no expected sha was provided, calculate actual sha to store on install
                if self.target_metadata:
                    self.target_metadata["sha256"] = get_file_sha256(installer_path)

            self.download_finished.emit(str(installer_path))

        except Exception as e:
            logger.error(f"Error al descargar actualización: {e}")
            self.error_occurred.emit(str(e))


class UpdateDialog(QDialog):
    def __init__(self, version, url, release_notes, target_metadata=None, update_reason="newer_version", parent=None):
        super().__init__(parent)
        self.version = version
        self.url = url
        self.target_metadata = target_metadata or {}
        self.update_reason = update_reason
        self.ignore_clicked = False
        self.setWindowTitle(t.get("update_available_title", "Update Available"))
        self.setWindowIcon(QIcon(str(ASSETS_DIR / "geforce.ico")))
        self.setFixedSize(400, 300)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setStyleSheet(GAMING_STYLESHEET)

        layout = QVBoxLayout()

        if self.update_reason in ("hotfix_hash_mismatch", "metadata_changed"):
            title_prefix = t.get("new_build_found", "New build/hotfix found:")
        else:
            title_prefix = t.get("new_version_found", "New version found:")

        lbl_title = QLabel(f"<b>{title_prefix} {version}</b>")
        lbl_title.setObjectName("title_label")
        lbl_title.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl_title)

        lbl_notes = QLabel(t.get("release_notes", "Release Notes:"))
        layout.addWidget(lbl_notes)

        self.notes_area = QScrollArea()
        self.notes_area.setWidgetResizable(True)
        self.notes_area.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")

        lang = get_current_lang()
        filtered_notes = filter_release_notes(release_notes, lang)

        self.notes_box = QLabel(filtered_notes)
        self.notes_box.setWordWrap(True)
        self.notes_box.setStyleSheet("background-color: #1a1b1d; padding: 10px; border-radius: 5px; color: #cfcfcf; border: 1px solid #2c2f33;")
        self.notes_box.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        
        self.notes_area.setWidget(self.notes_box)
        layout.addWidget(self.notes_area)
        
        layout.addStretch()

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        btn_layout = QHBoxLayout()
        self.btn_update = QPushButton(t.get("update_now", "Update Now"))
        self.btn_update.clicked.connect(self.start_download)
        self.btn_cancel = QPushButton(t.get("ignore_for_now", "Ignore for now"))
        self.btn_cancel.setObjectName("secondary")
        self.btn_cancel.clicked.connect(self.on_ignore_clicked)

        btn_layout.addWidget(self.btn_update)
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

        self.worker = None

    def on_ignore_clicked(self):
        self.ignore_clicked = True
        self.reject()

    def start_download(self):
        if getattr(sys, "frozen", False):
            install_dir = Path(sys.executable).parent
            try:
                test_file = install_dir / ".write_test"
                test_file.write_text("test")
                test_file.unlink()
            except Exception as e:
                logger.error(f"No write permissions in install directory: {e}")
                from src.ui.dialogs import GamingMessageBox
                GamingMessageBox.show_warning(
                    self, 
                    t.get("error_title", "Error"), 
                    t.get("permission_error_message", "No se tienen permisos de escritura en la carpeta de instalación. Intente ejecutar la aplicación como administrador o realice la actualización manualmente.")
                )
                self.btn_update.setEnabled(True)
                self.btn_cancel.setEnabled(True)
                return

        self.btn_update.setEnabled(False)
        self.btn_cancel.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        self.worker = UpdateWorker(mode="download", download_url=self.url, target_metadata=self.target_metadata)
        self.worker.download_progress.connect(self.progress_bar.setValue)
        self.worker.download_finished.connect(self.install_update)
        self.worker.error_occurred.connect(self.on_error)
        self.worker.start()

    def install_update(self, installer_path):
        try:
            logger.info(f"Launching installer: {installer_path}")
            
            # Prepare metadata to save on successful update
            build_to_save = dict(self.target_metadata)
            build_to_save["installed_at"] = datetime.now(timezone.utc).isoformat()
            
            if installer_path.lower().endswith(".zip") or installer_path.lower().endswith(".tar.gz"):
                if getattr(sys, "frozen", False):
                    from src.core.utils import IS_WINDOWS, IS_MACOS, IS_LINUX, USER_DATA_DIR
                    pid = os.getpid()
                    archive_path = str(installer_path)
                    install_dir = str(Path(sys.executable).parent)
                    exe_path = str(sys.executable)
                    flag_path = str(USER_DATA_DIR / "update_failed.json")
                    pending_build_path = str(USER_DATA_DIR / "installed_build.json.pending")
                    target_build_path = str(USER_DATA_DIR / "installed_build.json")
                    version_str = str(self.version)
                    
                    # Write pending build record before running update script
                    with open(pending_build_path, "w", encoding="utf-8") as f:
                        json.dump(build_to_save, f, indent=2)

                    if IS_WINDOWS:
                        # PowerShell auto-update for Windows
                        powershell_cmd = (
                            f"Start-Sleep -Seconds 1; "
                            f"while (Get-Process -Id {pid} -ErrorAction SilentlyContinue) {{ Start-Sleep -Milliseconds 100 }}; "
                            f"$temp_extract = Join-Path $env:TEMP ([Guid]::NewGuid().ToString()); "
                            f"$success = $true; "
                            f"try {{ "
                            f"  Expand-Archive -Path '{archive_path}' -DestinationPath $temp_extract -Force; "
                            f"  if (-not (Test-Path (Join-Path $temp_extract 'GeForceNOWRichPresence.exe'))) {{ "
                            f"    throw 'El archivo extraido no contiene GeForceNOWRichPresence.exe'; "
                            f"  }} "
                            f"  Remove-Item -Path '{install_dir}\\_internal' -Recurse -Force -ErrorAction SilentlyContinue; "
                            f"  Remove-Item -Path '{install_dir}\\lang' -Recurse -Force -ErrorAction SilentlyContinue; "
                            f"  Move-Item -Path \"$temp_extract\\*\" -Destination '{install_dir}' -Force; "
                            f"  if (Test-Path '{pending_build_path}') {{ "
                            f"    Move-Item -Path '{pending_build_path}' -Destination '{target_build_path}' -Force; "
                            f"  }} "
                            f"  Remove-Item -Path '{archive_path}' -Force; "
                            f"}} catch {{ "
                            f"  $success = $false; "
                            f"  if (Test-Path '{pending_build_path}') {{ Remove-Item -Path '{pending_build_path}' -Force -ErrorAction SilentlyContinue }}; "
                            f"  [System.Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms') | Out-Null; "
                            f"  [System.Windows.Forms.MessageBox]::Show('No se pudieron reemplazar los archivos de la aplicación debido a un error de escritura o falta de permisos.`n`nDetalle: ' + $_.Exception.Message, 'Error de Actualización', 0, 16); "
                            f"  $json = @{{ "
                            f"    timestamp = [double](Get-Date -UFormat %s); "
                            f"    version = '{version_str}'; "
                            f"    error = $_.Exception.Message; "
                            f"  }} | ConvertTo-Json; "
                            f"  Set-Content -Path '{flag_path}' -Value $json; "
                            f"}} finally {{ "
                            f"  Remove-Item -Path $temp_extract -Recurse -Force -ErrorAction SilentlyContinue; "
                            f"}}; "
                            f"if ($success) {{ "
                            f"  Start-Process -FilePath '{exe_path}'"
                            f"}}"
                        )
                        logger.info(f"Ejecutando auto-actualizador silencioso en segundo plano (Windows): {powershell_cmd}")
                        subprocess.Popen(
                            ["powershell", "-Command", powershell_cmd],
                            creationflags=subprocess.CREATE_NO_WINDOW
                        )
                        sys.exit(0)
                        
                    elif IS_MACOS:
                        # Bash auto-update for macOS
                        bash_cmd = (
                            f"sleep 1; "
                            f"while kill -0 {pid} 2>/dev/null; do sleep 0.1; done; "
                            f"temp_extract=$(mktemp -d); "
                            f"if unzip -o '{archive_path}' -d \"$temp_extract\" && [ -f \"$temp_extract/GeForceNOWRichPresence\" ]; then "
                            f"  rm -rf '{install_dir}/_internal' '{install_dir}/lang'; "
                            f"  cp -R \"$temp_extract\"/* '{install_dir}/'; "
                            f"  [ -f '{pending_build_path}' ] && mv -f '{pending_build_path}' '{target_build_path}'; "
                            f"  rm -f '{archive_path}'; "
                            f"  rm -rf \"$temp_extract\"; "
                            f"  open '{exe_path}'; "
                            f"else "
                            f"  [ -f '{pending_build_path}' ] && rm -f '{pending_build_path}'; "
                            f"  osascript -e 'display alert \"Error de Actualización\" message \"No se pudieron reemplazar los archivos de la aplicación por falta de permisos o error de descompresión.\"'; "
                            f"  echo \"{{\\\"timestamp\\\": $(date +%s), \\\"version\\\": \\\"{version_str}\\\", \\\"error\\\": \\\"Extraction failed on macOS\\\"}}\" > '{flag_path}'; "
                            f"  rm -rf \"$temp_extract\"; "
                            f"fi"
                        )
                        logger.info(f"Ejecutando auto-actualizador silencioso en segundo plano (macOS): {bash_cmd}")
                        subprocess.Popen(["bash", "-c", bash_cmd])
                        sys.exit(0)
                        
                    elif IS_LINUX:
                        # Bash auto-update for Linux
                        bash_cmd = (
                            f"sleep 1; "
                            f"while kill -0 {pid} 2>/dev/null; do sleep 0.1; done; "
                            f"temp_extract=$(mktemp -d); "
                            f"if tar -xzf '{archive_path}' -C \"$temp_extract\" && [ -f \"$temp_extract/GeForceNOWRichPresence\" ]; then "
                            f"  rm -rf '{install_dir}/_internal' '{install_dir}/lang'; "
                            f"  cp -R \"$temp_extract\"/* '{install_dir}/'; "
                            f"  [ -f '{pending_build_path}' ] && mv -f '{pending_build_path}' '{target_build_path}'; "
                            f"  rm -f '{archive_path}'; "
                            f"  rm -rf \"$temp_extract\"; "
                            f"  chmod +x '{exe_path}'; "
                            f"  '{exe_path}' & "
                            f"else "
                            f"  [ -f '{pending_build_path}' ] && rm -f '{pending_build_path}'; "
                            f"  zenity --error --text=\"No se pudieron reemplazar los archivos de la aplicación por falta de permisos o error de descompresión.\" 2>/dev/null || "
                            f"  kdialog --error \"No se pudieron reemplazar los archivos de la aplicación por falta de permisos o error de descompresión.\" 2>/dev/null; "
                            f"  echo \"{{\\\"timestamp\\\": $(date +%s), \\\"version\\\": \\\"{version_str}\\\", \\\"error\\\": \\\"Extraction failed on Linux\\\"}}\" > '{flag_path}'; "
                            f"  rm -rf \"$temp_extract\"; "
                            f"fi"
                        )
                        logger.info(f"Ejecutando auto-actualizador silencioso en segundo plano (Linux): {bash_cmd}")
                        subprocess.Popen(["bash", "-c", bash_cmd])
                        sys.exit(0)
                else:
                    save_installed_build(build_to_save)
                    msg = f"Modo de desarrollo: Actualización descargada en {installer_path}.\nLa auto-actualización silenciosa solo funciona en la versión compilada."
                    logger.info(msg)
                    from src.ui.dialogs import GamingMessageBox
                    GamingMessageBox.show_info(self, "Desarrollo", msg)
                    self.accept()
            else:
                # Launch installer wizard (.exe) on Windows if not a zip
                save_installed_build(build_to_save)
                subprocess.Popen([installer_path], shell=True)
                sys.exit(0)
        except Exception as e:
            self.on_error(f"Failed to launch installer: {e}")

    def on_error(self, msg):
        from src.ui.dialogs import GamingMessageBox
        GamingMessageBox.show_warning(self, "Error", msg)
        self.btn_update.setEnabled(True)
        self.btn_cancel.setEnabled(True)
        self.progress_bar.setVisible(False)


class Updater(QObject):
    update_status_changed = pyqtSignal()

    def __init__(self, config_manager=None, parent_widget=None):
        super().__init__()
        self.config_manager = config_manager
        self.parent_widget = parent_widget
        self.worker = None
        self.checking_updates = False
        self.update_available = False
        self.update_version = ""
        self.update_url = ""
        self.update_notes = ""
        self.target_metadata = {}
        self.update_reason = ""
        self.active_dialog = None

    def check_for_updates(self, silent=True):
        if silent:
            from src.core.utils import USER_DATA_DIR, safe_json_load
            flag_file = USER_DATA_DIR / "update_failed.json"
            if flag_file.exists():
                data = safe_json_load(flag_file)
                err_detail = ""
                if data and isinstance(data, dict):
                    err_detail = f" (Versión: {data.get('version', 'unknown')}, Error: {data.get('error', 'unknown')})"
                logger.warning(f"La última actualización falló{err_detail}. Se omitirá la comprobación de actualizaciones automática en esta sesión.")
                try:
                    flag_file.unlink()
                except Exception as e:
                    logger.error(f"No se pudo eliminar el archivo de registro de fallo: {e}")
                self.checking_updates = False
                self.update_available = False
                self.update_status_changed.emit()
                return

        if self.checking_updates:
            logger.info("Comprobación de actualizaciones ya en curso. Ignorando nueva solicitud.")
            return

        self.checking_updates = True
        self.worker = UpdateWorker(mode="check")
        self.worker.check_finished.connect(
            lambda has_update, ver, url, notes, meta, reason: self.on_check_finished(has_update, ver, url, notes, meta, reason, silent)
        )
        self.worker.error_occurred.connect(lambda msg: self.on_check_error(msg, silent))
        self.worker.start()

    def on_check_finished(self, has_update, version, url, notes, target_metadata, reason, silent):
        try:
            if has_update:
                self.update_available = True
                self.update_version = version
                self.update_url = url
                self.update_notes = notes
                self.target_metadata = target_metadata
                self.update_reason = reason
                self.update_status_changed.emit()

                # If silent, check if this version was already ignored and the time hasn't expired yet
                if silent and self.config_manager:
                    current_time = time.time()
                    last_ignored = self.config_manager.get_setting("updater_last_ignored_version", "")
                    ignore_until = self.config_manager.get_setting("updater_ignore_until", 0.0)
                    
                    if last_ignored == version and current_time < ignore_until:
                        logger.info(f"Actualización automática a {version} pospuesta hasta {time.ctime(ignore_until)} (ignorado).")
                        return

                self.show_update_dialog()
            else:
                self.update_available = False
                self.update_version = ""
                self.update_url = ""
                self.update_notes = ""
                self.target_metadata = {}
                self.update_reason = reason
                self.update_status_changed.emit()
                if not silent:
                    from src.ui.dialogs import GamingMessageBox
                    GamingMessageBox.show_info(self.parent_widget, t.get("no_updates", "No Updates"), t.get("latest_version_msg", "You are using the latest version."))
        finally:
            self.checking_updates = False

    def on_check_error(self, msg, silent):
        try:
            if not silent:
                from src.ui.dialogs import GamingMessageBox
                GamingMessageBox.show_warning(self.parent_widget, "Error", f"Error al comprobar actualizaciones: {msg}")
        finally:
            self.checking_updates = False

    def show_update_dialog(self):
        if not self.update_available:
            return

        if self.active_dialog is not None:
            try:
                self.active_dialog.raise_()
                self.active_dialog.activateWindow()
                return
            except RuntimeError:
                self.active_dialog = None

        self.active_dialog = UpdateDialog(
            self.update_version,
            self.update_url,
            self.update_notes,
            self.target_metadata,
            self.update_reason,
            self.parent_widget
        )
        self.active_dialog.exec_()
        
        ignore_clicked = self.active_dialog.ignore_clicked
        self.active_dialog = None
        
        if ignore_clicked:
            self.save_ignore_settings(self.update_version)
            self.update_status_changed.emit()

    def save_ignore_settings(self, version):
        if not self.config_manager:
            return
        
        current_time = time.time()
        last_ignored = self.config_manager.get_setting("updater_last_ignored_version", "")
        next_ignore_days = self.config_manager.get_setting("updater_next_ignore_days", 7)
        
        # Reset count if it's a new version
        if last_ignored != version:
            next_ignore_days = 7
        
        # postpone duration
        ignore_until = current_time + (next_ignore_days * 24 * 60 * 60)
        
        # next ignore duration
        escalated_next_days = min(next_ignore_days + 7, 21)
        
        self.config_manager.set_setting("updater_last_ignored_version", version)
        self.config_manager.set_setting("updater_next_ignore_days", escalated_next_days)
        self.config_manager.set_setting("updater_ignore_until", ignore_until)
        
        logger.info(f"Actualización a {version} ignorada por {next_ignore_days} días (hasta {time.ctime(ignore_until)}). Próximo aplazamiento será de {escalated_next_days} días.")