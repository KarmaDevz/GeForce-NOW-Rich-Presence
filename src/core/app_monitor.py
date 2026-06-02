import psutil
import subprocess
import logging
import sys

logger = logging.getLogger('geforce_presence')

class AppMonitor:
    @staticmethod
    def is_process_running(name: str) -> bool:
        for proc in psutil.process_iter(attrs=['name']):
            proc_name = (proc.info['name'] or "").lower()
            if name.lower() in proc_name:
                return True
            # Also handle cases with/without spaces for GeForce NOW on macOS
            if "geforcenow" in name.lower() and ("geforcenow" in proc_name or "geforce now" in proc_name):
                return True
        return False

    @staticmethod
    def kill_process(name: str):
        for proc in psutil.process_iter(attrs=['name']):
            proc_name = (proc.info['name'] or "").lower()
            match = name.lower() in proc_name
            if "geforcenow" in name.lower() and ("geforcenow" in proc_name or "geforce now" in proc_name):
                match = True
            if "dumb" in name.lower() and ("dumb.exe" in proc_name or "dumb.app" in proc_name or proc_name == "dumb"):
                match = True
                
            if match:
                try:
                    proc.kill()
                    logger.info(f"💀 Proceso {proc.info['name']} cerrado.")
                except psutil.NoSuchProcess:
                    pass
                except Exception as e:
                    logger.error(f"⚠️ No se pudo cerrar {proc.info['name']}: {e}")

    @staticmethod
    def monitor_geforce_and_dumb():
        is_running = False
        if sys.platform == "win32":
            is_running = AppMonitor.is_process_running("GeForceNOW.exe")
        elif sys.platform == "darwin":
            is_running = AppMonitor.is_process_running("GeForceNOW") or AppMonitor.is_process_running("GeForce NOW")
        else:
            is_running = AppMonitor.is_process_running("GeForceNOW")

        if not is_running:
            if sys.platform == "win32":
                AppMonitor.kill_process("dumb.exe")
            elif sys.platform == "darwin":
                # AppMonitor.kill_process("dumb")
                # AppMonitor.kill_process("dumb.app")
                pass

    @staticmethod
    def launch_dumb(path_dumb: str):
        if sys.platform == "win32":
            AppMonitor.kill_process("dumb.exe")
            subprocess.Popen([path_dumb])
            logger.info("🚀 dumb.exe iniciado.")
        elif sys.platform == "darwin":
            # AppMonitor.kill_process("dumb")
            # AppMonitor.kill_process("dumb.app")
            # subprocess.Popen(["open", "-n", "-a", path_dumb])
            # logger.info("🚀 dumb.app iniciado.")
            pass
