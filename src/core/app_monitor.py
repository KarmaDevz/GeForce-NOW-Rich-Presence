import psutil
import subprocess
import logging
import os
import sys
from src.core.utils import get_lang_from_registry, load_locale

try:
    LANG = get_lang_from_registry()
except Exception:
    LANG = os.getenv('GEFORCE_LANG', 'en')
TEXTS = load_locale(LANG)

logger = logging.getLogger('geforce_presence')

class AppMonitor:
    @staticmethod
    def is_process_running(name: str) -> bool:
        for proc in psutil.process_iter(attrs=['name']):
            if name.lower() in (proc.info['name'] or "").lower():
                return True
        return False

    @staticmethod
    def kill_process(name: str):
        for proc in psutil.process_iter(attrs=['name']):
            if name.lower() in (proc.info['name'] or "").lower():
                try:
                    proc.kill()
                    logger.info(TEXTS.get("kill_process", "💀 Proceso {name} cerrado.").format(name=name))
                except psutil.NoSuchProcess:
                    pass
                except Exception as e:
                    logger.error(TEXTS.get("kill_process_error", "⚠️ No se pudo cerrar {name}: {e}").format(name=name, e=e))

    @staticmethod
    def monitor_geforce_and_dumb():
        if sys.platform != "win32":
            return
        
        if not AppMonitor.is_process_running("GeForceNOW.exe"):
            AppMonitor.kill_process("dumb.exe")

    @staticmethod
    def launch_dumb(path_dumb: str):
        if sys.platform != "win32":
            return
        
        AppMonitor.kill_process("dumb.exe")
        subprocess.Popen([path_dumb])
        logger.info(TEXTS.get("launching_dumb", "🚀 dumb.exe iniciado."))
