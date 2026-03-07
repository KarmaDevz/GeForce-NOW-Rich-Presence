import json
import os
import sys
try:
    import winreg
except ImportError:
    winreg = None
import subprocess
from pathlib import Path

IS_WINDOWS = sys.platform.startswith("win")
IS_LINUX = sys.platform.startswith("linux")
IS_MACOS = sys.platform.startswith("darwin")

def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

LANG_DIR = Path(resource_path("lang"))

def get_lang_from_registry(default="en"):
    if IS_WINDOWS:
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\GeForcePresence")
            lang, _ = winreg.QueryValueEx(key, "lang")
            winreg.CloseKey(key)
            return _normalize_lang(lang, default)
        except Exception:
            return default
    elif IS_MACOS:
        try:
            # Try reading from macOS defaults
            # defaults read com.nvidia.geforcenow lang
            # Note: This assumes the app stores it there, or we check system lang
            result = subprocess.run(
                ["defaults", "read", "com.nvidia.geforcenow", "lang"],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                return _normalize_lang(result.stdout.strip(), default)
        except Exception:
            pass
        
        # Fallback to system locale
        lang = os.getenv("LANG", default)
        return _normalize_lang(lang, default)
    
    elif IS_LINUX:
        lang = os.getenv("LANG", default)
        if "." in lang:
            lang = lang.split(".")[0]
        return _normalize_lang(lang, default)

    return default

def _normalize_lang(lang_str: str, default: str) -> str:
    lang_str = lang_str.lower()
    if "spanish" in lang_str or "es" in lang_str:
        return "es"
    elif "english" in lang_str or "en" in lang_str:
        return "en"
    return default

def load_locale(lang: str = "en") -> dict:
    path = LANG_DIR / f"{lang}.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass # Fallback to default if file is corrupted
            
    # Fallback to default language
    default_path = LANG_DIR / "en.json"
    if default_path.exists():
         return json.loads(default_path.read_text(encoding="utf-8"))
    return {}

class Translator:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Translator, cls).__new__(cls)
            cls._instance.texts = {}
            cls._instance.lang = "en"
            cls._instance.load_language()
        return cls._instance

    def load_language(self):
        try:
            self.lang = get_lang_from_registry()
            self.texts = load_locale(self.lang)
        except Exception:
            self.lang = os.getenv('GEFORCE_LANG', 'en')
            self.texts = load_locale(self.lang)

    def get(self, key, default=None):
        return self.texts.get(key, default)

    def __getitem__(self, key):
        return self.texts.get(key, key) # Return key if not found

# Global instance
t = Translator()
