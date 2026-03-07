import os
import psutil
import subprocess
import logging
import json
import time
import shutil
import sys
from pathlib import Path
from typing import Optional
from src.core.utils import get_lang_from_registry, load_locale

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
        if sys.platform == "win32":
            possible = [
                Path(os.getenv("LOCALAPPDATA", "")) / "NVIDIA Corporation" / "GeForceNOW" / "CEF" / "GeForceNOW.exe"
            ]
            for p in possible:
                if p.exists():
                    return str(p)
        else:
            if shutil.which("flatpak"):
                return "flatpak run com.nvidia.geforcenow"
        
        return None

    @staticmethod
    def _is_process_running_by_name(target_name: str) -> bool:
        try:
            for proc in psutil.process_iter(attrs=['name']):
                name = (proc.info.get('name') or "").lower()
                if name == target_name.lower() or target_name.lower() in name:
                    return True
        except Exception:
            pass
        return False

    @staticmethod
    def kill_process_by_name(target_name: str):
        try:
            for proc in psutil.process_iter(attrs=['name']):
                name = (proc.info.get('name') or "").lower()
                if name == target_name.lower() or target_name.lower() in name:
                    proc.kill()
        except Exception as e:
            logger.error(f"Error al cerrar {target_name}: {e}")

    @staticmethod
    def disable_native_rich_presence() -> tuple[bool, bool]:
        """
        Deshabilita el Rich Presence nativo de GeForce NOW en el archivo sharedstorage.json.
        Retorna (success, modified)
        """
        config_path = Path(os.environ.get("LOCALAPPDATA", "")) / "NVIDIA Corporation" / "GeForceNOW" / "sharedstorage.json"
        
        if not config_path.exists():
            logger.warning(TEXTS.get("gfn_config_not_found", "Archivo no encontrado: sharedstorage.json"))
            return False, False
            
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"JSON corrupto o error de lectura: {e}")
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
                logger.info("Flag modificado. Operación completada correctamente.")
                return True, True
            else:
                logger.info("Flag ya deshabilitado. Operación completada correctamente.")
                return True, False
        except Exception as e:
            logger.error(f"Error inesperado al procesar JSON: {e}")
            return False, False
        
        if sys.platform != "win32":
	        return False, False    

    @staticmethod
    def launch_geforce_now() -> bool:
        success, modified = AppLauncher.disable_native_rich_presence()
        
        proc_name = "GeForceNOW.exe" if sys.platform == "win32" else "GeForceNOW"
        is_running = AppLauncher._is_process_running_by_name(proc_name)
        
        if is_running:
            if modified:
                logger.info("Reiniciando GeForce NOW para aplicar la desactivación del Rich Presence nativo...")
                AppLauncher.kill_process_by_name("GeForceNOW.exe")
                time.sleep(1.5)  # Esperar a que se cierre completamente
            else:
                logger.info(TEXTS.get("already_running", "💡 GeForce NOW is already running"))
                return True

        path = AppLauncher.find_geforce_now()
        if path:
            logger.info(TEXTS.get("launching", "🚀 Launching GeForce NOW..."))
            
            if sys.platform == "win32":
                subprocess.Popen([path])
            else:
                subprocess.Popen(["flatpak", "run", "com.nvidia.geforcenow"])
    
            return True
        else:
            logger.error(TEXTS.get("geforce_not_found", "GeForce NOW not found in the default installation path."))
            return False

    @staticmethod
    def find_discord() -> Optional[str]:
        if sys.platform == "win32":
            p = Path(os.getenv("LOCALAPPDATA", "")) / "Discord" / "Update.exe"
        if p.exists():
            return str(p)
        else:
            return shutil.which("discord")
        return None

    @staticmethod
    def launch_discord():
        for proc in psutil.process_iter(attrs=['name']):
            name = (proc.info.get('name') or "").lower()
            if "discord" in name and "update" not in name:
                logger.info(TEXTS.get("already_running_discord", "💡 Discord ya está en ejecución"))
                return
        updater = AppLauncher.find_discord()
        if updater:
            logger.info(TEXTS.get("launching_discord", "🚀 Iniciando Discord..."))
            
            if sys.platform == "win32":
                subprocess.Popen([updater, "--processStart", "Discord.exe"])
            else:
                subprocess.Popen([updater])
        else:
            logger.warning("⚠️ No se encontró Discord instalado en la ruta por defecto.")
