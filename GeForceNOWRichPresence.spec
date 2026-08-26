# -*- mode: python ; coding: utf-8 -*-
import sys


a = Analysis(
    ['src/GeForceNOWRichPresence.py'],
    pathex=[],
    binaries=[],
    datas=[('src', 'src'), ('tools', 'tools'), ('lang', 'lang'), ('config', 'config'), ('assets', 'assets')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='GeForceNOWRichPresence',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version='version.txt' if sys.platform == 'win32' else None,
    icon=['assets/gfn.ico'] if sys.platform == 'win32' else None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='GeForceNOWRichPresence',
)
