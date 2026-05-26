import os
import sys
import psutil
import subprocess
import logging
import json
import time
from pathlib import Path
from typing import Optional
from src.core.utils import get_lang_from_registry, load_locale, IS_WINDOWS, IS_LINUX, IS_MACOS

try:
    LANG = get_lang_from_registry()
    TEXTS = load_locale(LANG)
except Exception:
    LANG = os.getenv('GEFORCE_LANG', 'en')
    TEXTS = load_locale(LANG)

logger = logging.getLogger('geforce_presence')

class AppLauncher:
    @staticmethod
    def find_geforce_now() -> Optional[str]:
        if IS_WINDOWS:
            possible = [
                Path(os.getenv("LOCALAPPDATA", "")) / "NVIDIA Corporation" / "GeForceNOW" / "CEF" / "GeForceNOW.exe"
            ]
            for p in possible:
                if p.exists():
                    return str(p)
        elif IS_LINUX:
            # Check for native GFN client (Electron-based, if installed)
            linux_paths = [
                Path.home() / ".local" / "share" / "applications" / "geforcenow.desktop",
                Path("/usr/share/applications/geforcenow.desktop"),
                Path("/opt/geforcenow/GeForceNOW"),
            ]
            for p in linux_paths:
                if p.exists():
                    return str(p)
            
            # Check for flatpak
            try:
                result = subprocess.run(
                    ['flatpak', 'list', '--app', '--columns=application'],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0 and 'com.nvidia.geforcenow' in result.stdout.lower():
                    return 'flatpak:com.nvidia.geforcenow'
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass
            
            # Fallback: return URL to open in browser
            return "https://play.geforcenow.com"
        elif IS_MACOS:
            mac_paths = [
                Path("/Applications/GeForceNOW.app"),
                Path.home() / "Applications" / "GeForceNOW.app",
            ]
            for p in mac_paths:
                if p.exists():
                    return str(p)
            
        return None

    @staticmethod
    def _is_process_running_by_name(target_name: str) -> bool:
        try:
            target_lower = target_name.lower()
            for proc in psutil.process_iter(attrs=['name']):
                name = (proc.info.get('name') or "").lower()
                if name == target_lower or target_lower in name:
                    return True
        except Exception:
            pass
        return False

    @staticmethod
    def kill_process_by_name(target_name: str):
        try:
            target_lower = target_name.lower()
            for proc in psutil.process_iter(attrs=['name']):
                name = (proc.info.get('name') or "").lower()
                if name == target_lower or target_lower in name:
                    proc.kill()
        except Exception as e:
            logger.error(f"Error closing {target_name}: {e}")

    @staticmethod
    def disable_native_rich_presence() -> tuple[bool, bool]:
        """
        Disables GFN native Rich Presence in the sharedstorage.json file.
        Returns (success, modified)
        """
        if IS_LINUX:
            # On Linux, GFN usually runs in browser — no native config to disable
            logger.debug("Linux: GFN native Rich Presence config not applicable (browser-based)")
            return True, False
            
        config_path = Path(os.environ.get("LOCALAPPDATA", "")) / "NVIDIA Corporation" / "GeForceNOW" / "sharedstorage.json"
        
        if not config_path.exists():
            logger.warning(TEXTS.get("gfn_config_not_found", "File not found: sharedstorage.json"))
            return False, False
            
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Corrupt JSON or read error: {e}")
            return False, False
            
        try:
            if "appSettingsConfig" not in data:
                data["appSettingsConfig"] = {}
                
            app_settings = data["appSettingsConfig"]
            modified = False
            
            if "discordRpEnabled" not in app_settings:
                modified = True
            elif app_settings["discordRpEnabled"] is True:
                modified = True
                
            if modified:
                new_app_settings = {}
                for k, v in app_settings.items():
                    if k == "discordRpEnabled":
                        continue
                    new_app_settings[k] = v
                    if k == "clipboardPaste":
                        new_app_settings["discordRpEnabled"] = False
                        
                if "discordRpEnabled" not in new_app_settings:
                    new_app_settings["discordRpEnabled"] = False
                    
                data["appSettingsConfig"] = new_app_settings
                
                with open(config_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, separators=(',', ':'))
                logger.info("Flag modified. Operation completed successfully.")
                return True, True
            else:
                logger.info("Flag already disabled. Operation completed successfully.")
                return True, False
        except Exception as e:
            logger.error(f"Unexpected error processing JSON: {e}")
            return False, False

    @staticmethod
    def launch_geforce_now() -> bool:
        success, modified = AppLauncher.disable_native_rich_presence()
        
        if IS_WINDOWS:
            process_name = "GeForceNOW.exe"
        elif IS_LINUX:
            process_name = "geforcenow"
        else:
            process_name = "GeForceNOW"
            
        is_running = AppLauncher._is_process_running_by_name(process_name)
        
        if is_running:
            if modified:
                logger.info("Restarting GeForce NOW to apply native Rich Presence disable...")
                AppLauncher.kill_process_by_name(process_name)
                time.sleep(1.5)
            else:
                logger.info(TEXTS.get("already_running", "💡 GeForce NOW is already running"))
                return True

        path = AppLauncher.find_geforce_now()
        if path:
            logger.info(TEXTS.get("launching", "🚀 Launching GeForce NOW..."))
            if IS_LINUX:
                if path.startswith("https://"):
                    # Open in browser
                    subprocess.Popen(['xdg-open', path])
                elif path.startswith("flatpak:"):
                    app_id = path.split(":", 1)[1]
                    subprocess.Popen(['flatpak', 'run', app_id])
                elif path.endswith('.desktop'):
                    subprocess.Popen(['xdg-open', path])
                else:
                    subprocess.Popen([path])
            elif IS_MACOS:
                subprocess.Popen(['open', '-a', path])
            else:
                subprocess.Popen([path])
            return True
        else:
            if IS_LINUX:
                # Fallback: open GFN in browser
                logger.info("🐧 Opening GeForce NOW in browser...")
                subprocess.Popen(['xdg-open', 'https://play.geforcenow.com'])
                return True
            logger.error(TEXTS.get("geforce_not_found", "GeForce NOW not found. Start it manually."))
            return False

    @staticmethod
    def find_discord() -> Optional[str]:
        if IS_WINDOWS:
            p = Path(os.getenv("LOCALAPPDATA", "")) / "Discord" / "Update.exe"
            if p.exists():
                return str(p)
        elif IS_LINUX:
            # Check common Linux Discord locations
            linux_discord_paths = [
                "/usr/bin/discord",
                "/usr/bin/Discord",
                str(Path.home() / ".local" / "bin" / "discord"),
                "/opt/discord/Discord",
                "/snap/bin/discord",
            ]
            for p in linux_discord_paths:
                if Path(p).exists():
                    return p
            
            # Check for flatpak Discord
            try:
                result = subprocess.run(
                    ['flatpak', 'list', '--app', '--columns=application'],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0 and 'com.discordapp.Discord' in result.stdout:
                    return 'flatpak:com.discordapp.Discord'
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass
            
            # Check PATH
            import shutil
            discord_in_path = shutil.which("discord") or shutil.which("Discord")
            if discord_in_path:
                return discord_in_path
        elif IS_MACOS:
            mac_paths = [
                "/Applications/Discord.app",
                str(Path.home() / "Applications" / "Discord.app"),
            ]
            for p in mac_paths:
                if Path(p).exists():
                    return p
        return None

    @staticmethod
    def launch_discord():
        for proc in psutil.process_iter(attrs=['name']):
            name = (proc.info.get('name') or "").lower()
            if "discord" in name and "update" not in name:
                logger.info(TEXTS.get("already_running_discord", "💡 Discord is already running"))
                return
        discord_path = AppLauncher.find_discord()
        if discord_path:
            logger.info(TEXTS.get("launching_discord", "🚀 Launching Discord..."))
            if IS_LINUX:
                if discord_path.startswith("flatpak:"):
                    app_id = discord_path.split(":", 1)[1]
                    subprocess.Popen(['flatpak', 'run', app_id])
                else:
                    subprocess.Popen([discord_path])
            elif IS_WINDOWS:
                subprocess.Popen([discord_path, "--processStart", "Discord.exe"])
            elif IS_MACOS:
                subprocess.Popen(['open', '-a', discord_path])
        else:
            logger.warning("⚠️ Discord installation not found in the default path.")
