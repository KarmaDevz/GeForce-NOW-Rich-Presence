# BUILDING THE EXECUTABLE

make sure to install the deps (updated ones) `pip install -r requirements.txt`

build the binary with pyinstaller, an example of what i did
```
pyinstaller --clean --noconfirm \
    --name GeForce_NOW_Rich_Presence \
    --icon assets/gfn.ico \
    --add-data "assets:assets" \
    --add-data "lang:lang" \
    --add-data "config:config" \
    --add-data "tools:tools" \
    src/GeForceNOWRichPresence.py
```
make sure the binary is executable `chmod +x`

# BUILDING THE APPIMAGE    
make the appdir structure for making the appimage
```
AppDir/
├── GeForceNOWRichPresence.desktop # makes a shortcut
├── gfn.png # the icon for the app
├── AppRun
└── usr
    ├── bin
    │   └── GeForceNOWRichPresence # the executable itself, make sure its executable
    └── share
        └── geforce_presence # name the folder whatever
            ├── assets # include ALL relevant files for these
            ├── config
            ├── lang
            └── tools
```
an example of the .dekstop
```
[Desktop Entry]
Type=Application
Name=GeForce NOW Presence
Comment=Shows GeForce NOW status in Discord
Exec=GeForceNOWRichPresence
Icon=gfn
Terminal=false
Categories=Utility;
```
make AppRun and make it executable too
```
#!/bin/bash
HERE="$(dirname "$(readlink -f "${0}")")"
exec "$HERE/usr/bin/GeForceNOWRichPresence" "$@"
```
and build it with `appimagetool AppDir`
