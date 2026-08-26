import sys
import os
import logging
from pathlib import Path
from typing import Optional, Dict

from src.core.utils import IS_WINDOWS, ASSETS_DIR

logger = logging.getLogger('geforce_presence')
APP_USER_MODEL_ID = "KarmaDevz.GeForcePresence"

def setup_jumplist(texts: Optional[Dict[str, str]] = None) -> bool:
    """
    Registers custom JumpList tasks in the Windows Taskbar context menu.
    """
    if not IS_WINDOWS:
        return False
        
    try:
        import pythoncom
        from win32com.shell import shell
        import win32com.propsys.propsys as propsys
        import win32com.propsys.pscon as pscon
        
        # 1. Set explicit AppUserModelID for the process
        shell.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
        
        # 2. Instantiate DestinationList
        dest_list = pythoncom.CoCreateInstance(
            shell.CLSID_DestinationList,
            None,
            pythoncom.CLSCTX_INPROC_SERVER,
            shell.IID_ICustomDestinationList
        )
        dest_list.SetAppID(APP_USER_MODEL_ID)
        min_slots, removed = dest_list.BeginList()
        
        # 3. Create collection of tasks
        collection = pythoncom.CoCreateInstance(
            shell.CLSID_EnumerableObjectCollection,
            None,
            pythoncom.CLSCTX_INPROC_SERVER,
            shell.IID_IObjectCollection
        )
        
        # 4. Create Task: "Ver Registros (Logs)"
        task_title = (texts or {}).get("jumplist_view_logs", "Ver Registros (Logs)")
        task_desc = (texts or {}).get("jumplist_view_logs_desc", "Abrir el visor de registros de GeForce Presence")
        
        link = pythoncom.CoCreateInstance(
            shell.CLSID_ShellLink,
            None,
            pythoncom.CLSCTX_INPROC_SERVER,
            shell.IID_IShellLinkW
        )
        
        if getattr(sys, "frozen", False):
            exe_path = str(sys.executable)
            link.SetPath(exe_path)
            link.SetArguments("--logs")
            link.SetIconLocation(exe_path, 0)
        else:
            # In development mode, run python.exe -m src.GeForceNOWRichPresence --logs
            exe_path = str(sys.executable)
            main_script = str(Path(__file__).resolve().parent.parent / "GeForceNOWRichPresence.py")
            link.SetPath(exe_path)
            link.SetArguments(f'"{main_script}" --logs')
            ico_path = ASSETS_DIR / "geforce.ico"
            if ico_path.exists():
                link.SetIconLocation(str(ico_path), 0)
                
        link.SetDescription(task_desc)
        
        # Set task title in property store
        prop_store = link.QueryInterface(propsys.IID_IPropertyStore)
        prop_store.SetValue(pscon.PKEY_Title, propsys.PROPVARIANTType(task_title, pythoncom.VT_LPWSTR))
        prop_store.Commit()
        
        collection.AddObject(link)
        
        # 5. Commit tasks to destination list
        dest_list.AddUserTasks(collection)
        dest_list.CommitList()
        logger.info("📋 Windows JumpList configurada correctamente.")
        return True
        
    except Exception as e:
        logger.debug(f"No se pudo registrar la JumpList de Windows: {e}")
        return False
