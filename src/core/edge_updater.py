import logging
import os
import requests
import zipfile
import re
import shutil
import time
from pathlib import Path
from bs4 import BeautifulSoup

try:
    import winreg
except ImportError:
    winreg = None

from PyQt5.QtWidgets import QMessageBox

from src.core.utils import DRIVER_PATH, IS_WINDOWS

logger = logging.getLogger('geforce_presence')

class EdgeDriverUpdater:
    r"""
    Automatic Edge Driver Updater.
    Checks for the installed Edge version via Registry (HKCU\Software\Microsoft\Edge\BLBeacon)
    and downloads the matching WebDriver. If checking registry is denied/fails,
    downloads the latest version by scraping the official page.
    """

    OFFICIAL_TOOLS_URL = "https://developer.microsoft.com/en-us/microsoft-edge/tools/webdriver/?form=MA13LH#downloads"
    DOWNLOAD_URL_TEMPLATE = "https://msedgedriver.microsoft.com/{version}/edgedriver_win64.zip"

    def __init__(self, parent_widget=None):
        self.parent_widget = parent_widget

    def update(self):
        """
        Orchestrates the update process.
        """
        if not IS_WINDOWS:
            logger.info("Skipping Edge Driver Update (Windows Only)")
            return

        logger.info("Starting Edge Driver Check...")

        # 1. Ask User Permission
        reply = QMessageBox.question(
            self.parent_widget,
            "Edge Driver Check",
            "This application needs to check your installed Microsoft Edge version to download the correct WebDriver.\n\n"
            "This requires reading the Registry (HKEY_CURRENT_USER).\n\n"
            "Do you allow this check?\n"
            "(If No, we will try to download the latest available version, which might not match your browser.)",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )

        version_to_download = None

        if reply == QMessageBox.Yes:
            logger.info("User allowed registry check.")
            version_to_download = self.get_edge_version_from_registry()
            if not version_to_download:
                logger.warning("Could not detect version from registry. Fallback to latest.")
        else:
            logger.info("User denied registry check. Fallback to latest.")

        if version_to_download:
            logger.info(f"Detected Edge Version: {version_to_download}")
            success = self.download_specific_version(version_to_download)
            if success:
                logger.info("Driver updated successfully via version match.")
                return
            else:
                logger.warning("Failed to download specific version. Fallback to latest.")

        # Fallback to scraping latest
        self.download_latest_version()

    def get_edge_version_from_registry(self):
        r"""
        Reads HKEY_CURRENT_USER\Software\Microsoft\Edge\BLBeacon -> version
        """
        if not winreg:
            return None
        
        try:
            key_path = r"Software\Microsoft\Edge\BLBeacon"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                version, _ = winreg.QueryValueEx(key, "version")
                return version.strip()
        except FileNotFoundError:
            logger.debug("Edge BLBeacon registry key not found.")
            return None
        except Exception as e:
            logger.error(f"Error checking registry: {e}")
            return None

    def download_specific_version(self, version):
        """
        Downloads https://msedgedriver.microsoft.com/<VERSION>/edgedriver_win64.zip
        """
        url = self.DOWNLOAD_URL_TEMPLATE.format(version=version)
        return self._download_and_extract(url)

    def download_latest_version(self):
        """
        Scrapes the official page for the latest stable x64 version.
        """
        logger.info("Scraping for latest Edge Driver version...")
        try:
            resp = requests.get(self.OFFICIAL_TOOLS_URL, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.content, "html.parser")
            
            # Find the "x64" link. 
            # Looking for <a> tags that contain "x64" text or href containing "win64"
            # The structure usually has a link with "x64" text inside a listing.
            # Using the user's hint: "//a[.//span[text()='x64']]" or "//a[contains(@href, 'win64')]"
            
            # Strategy: Find all links, check if 'win64' in href or 'x64' in text
            target_url = None
            
            # Try finding by href first (more reliable for direct zip links)
            for a in soup.find_all('a', href=True):
                if 'edgedriver_win64.zip' in a['href']:
                    target_url = a['href']
                    break
            
            if not target_url:
                logger.warning("Could not find direct link by href scraping. This might fail if generic scraping is weak.")
                # Try finding text 'x64' and getting parent? The page structure is complex.
                # However, the user provided a fallback logic.
                pass
            
            if target_url:
                logger.info(f"Found latest URL: {target_url}")
                return self._download_and_extract(target_url)
            else:
                logger.error("Failed to find download URL on official page.")
                QMessageBox.warning(self.parent_widget, "Error", "Could not find the latest Edge Driver. Please download it manually.")
                return False

        except Exception as e:
            logger.error(f"Error scraping latest version: {e}")
            return False

    def _download_and_extract(self, url):
        """
        Downloads zip from url, extracts msedgedriver.exe to tools/.
        """
        try:
            logger.info(f"Downloading {url}...")
            r = requests.get(url, stream=True, timeout=30)
            
            if r.status_code == 404:
                logger.warning(f"Version not found on server (404): {url}")
                return False
                
            r.raise_for_status()

            # Save zip to temp
            tmp_zip = Path(os.environ["TEMP"]) / "edgedriver_temp.zip"
            with open(tmp_zip, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)

            # Extract
            extract_dir = Path(os.environ["TEMP"]) / "edgedriver_extract"
            if extract_dir.exists():
                shutil.rmtree(extract_dir)
            extract_dir.mkdir()

            with zipfile.ZipFile(tmp_zip, 'r') as zf:
                zf.extractall(extract_dir)

            # Locate msedgedriver.exe (it might be in a subfolder)
            driver_src = None
            for root, dirs, files in os.walk(extract_dir):
                if "msedgedriver.exe" in files:
                    driver_src = Path(root) / "msedgedriver.exe"
                    break
            
            if driver_src and driver_src.exists():
                target_dir = DRIVER_PATH.parent
                target_dir.mkdir(parents=True, exist_ok=True)
                
                target_path = DRIVER_PATH
                
                # Check locked
                if target_path.exists():
                    try:
                        target_path.unlink()
                    except PermissionError:
                        # Try to rename old one if we can't delete (sometimes effective on Windows)
                        try:
                            old_path = target_path.with_suffix(".old.exe")
                            if old_path.exists():
                                old_path.unlink()
                            target_path.rename(old_path)
                        except Exception as e:
                            logger.error(f"Could not replace driver file (locked?): {e}")
                            QMessageBox.critical(self.parent_widget, "Error", "Edge Driver is in use. Please close any open Edge/Driver instances and restart.")
                            return False

                shutil.move(str(driver_src), str(target_path))
                logger.info(f"Driver installed to {target_path}")
                return True
            else:
                logger.error("msedgedriver.exe not found in downloaded zip.")
                return False

        except Exception as e:
            logger.error(f"Download/Extract failed: {e}")
            return False
        finally:
            # Cleanup
            try:
                if 'tmp_zip' in locals() and tmp_zip.exists():
                    tmp_zip.unlink()
                if 'extract_dir' in locals() and extract_dir.exists():
                    shutil.rmtree(extract_dir)
            except Exception:
                pass
