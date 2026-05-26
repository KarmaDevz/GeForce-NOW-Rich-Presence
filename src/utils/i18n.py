import json
import os
import sys
try:
    import winreg
except ImportError:
    winreg = None  # Linux için
from pathlib import Path

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
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\GeForcePresence")
        lang, _ = winreg.QueryValueEx(key, "lang")
        winreg.CloseKey(key)

        if "spanish" in lang.lower():
            return "es"
        elif "english" in lang.lower():
            return "en"
        else:
            return default
    except Exception:
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
