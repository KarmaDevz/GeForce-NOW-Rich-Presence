<div align="center">
  <img src="assets/asset1.jpg" alt="GeForce NOW Rich Presence Banner" width="100%" style="border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.2);" />
  <br/>
  <h1>🎮 GeForce NOW Rich Presence for Discord</h1>
  <p>
    <strong>Show your real game on Discord while playing on GeForce NOW — automatically and beautifully.</strong>
  </p>
  
  [🇪🇸 Leer en Español](./README.es.md) • [🇷🇺 На русском](./README.ru.md) • [📥 Download Latest](#-installation) • [💬 Support](#-about--support)
  
  <br/>

  <a href="https://github.com/KarmaDevz/GeForce-NOW-Rich-Presence/releases/latest">
    <img src="https://img.shields.io/github/v/release/KarmaDevz/GeForce-NOW-Rich-Presence?style=for-the-badge&color=00C853&logo=github&label=Latest%20Release" alt="Latest Release"/>
  </a>
  <a href="https://github.com/KarmaDevz/GeForce-NOW-Rich-Presence/releases">
    <img src="https://img.shields.io/github/downloads/KarmaDevz/GeForce-NOW-Rich-Presence/total?style=for-the-badge&color=2962FF&logo=github&label=Downloads" alt="Total Downloads"/>
  </a>
  <img src="https://img.shields.io/badge/Platforms-Windows%20%7C%20macOS%20%7C%20Linux-brightgreen?style=for-the-badge" alt="Supported Platforms"/>
  
</div>

---

## 🕹️ What is this?

By default, Discord only displays a generic **"Playing NVIDIA GeForce NOW"** status when you stream games. This application runs quietly in your system tray, scans your active GeForce NOW stream, matches it against a local database, and replaces it with the **actual game name, description, active party size, and matching game artwork** on your Discord profile in real time.

---

## ✨ Features

- 🔍 **Dynamic Game Detection**: Automatically tracks games running on GeForce NOW via active window parsing.
- 🎯 **Quest Mode (Discord Quests)**: Simultaneously queue and simulate multiple game instances to complete Discord Quests (each simulation runs for 16 minutes and 30 seconds before auto-closing).
- 🔑 **Steam Cookie Manager**: Safely extracts your local Steam session cookie via Selenium and `browser-cookie3` to fetch deep Steam lobby details, player counts, and rich game states.
- 🛠️ **Diagnostics Hub**: Built-in, syntax-highlighted log viewer and an automatic crash reporter dialog to copy tracebacks instantly.
- 🔄 **Multi-Platform Silent Updates**: Built-in silent background updater that detects, downloads, and extracts updates dynamically for Windows, macOS, and Linux without prompt loops.
- 🚀 **Autostart Toggles**: Easily configure start-with-OS preferences directly from the system tray menu.
- 💻 **100% Cross-Platform**: Native builds and support for Windows, macOS, and Linux.

---

## 📸 In Action

<div align="center">
  <img src="assets/instructions.png" width="95%" alt="Discord Rich Presence Instructions" style="border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.2);"/>
</div>

---

## ⚙️ Tray Icon Options

Access configuration and features directly from the system tray menu:

| Category | Option | Description |
| :--- | :--- | :--- |
| **Actions** | 🎮 **Force Game...** | Manually override detection and choose a specific game to display. |
| | 📊 **Sync Games** | Fetch the latest game-matching mappings database from the cloud. |
| | 👥 **Quest Mode...** | Open the Quest list panel to add, monitor, and clean up active quest game simulations. |
| **Credentials**| 🔑 **Obtain Steam Cookie** | Authenticate and pull cookie information for deeper Steam integration. |
| **Preferences**| ⚙️ **Autostart Preferences** | Toggle start-with-OS (Windows startup folder shortcut management). |
| | 📥 **Install Update** | Displayed only when a new version is ready to download. |
| **System** | 📝 **Herramientas de diagnóstico** | Access the live app logs viewer. |
| | ℹ️ **About** | View application information and the current version. |
| | ❌ **Exit** | Fully terminate the application and close all background processes. |

---

## 🛠️ Technology Stack & Architecture

This application is built with modern, efficient Python libraries:
* **UI Framework**: `PyQt5` for a responsive, theme-matching dark gaming style desktop client.
* **Discord Integration**: `pypresence` for low-latency Discord RPC communication.
* **Process Tracking**: `psutil` to safely monitor GeForce NOW and clean up orphaned fake/simulation executables.
* **Browser Automation**: `selenium` and `browser-cookie3` to scrape local browser data securely.
* **Packaging**: `PyInstaller` for creating portable, lightweight standalone application packages.
* **CI/CD Build Pipeline**: `GitHub Actions` matrix builds to compile executables natively on Windows, macOS, and Linux runners.

---

## 📥 Installation

### Windows
1. Download the installer (`GeForcePresenceSetup.exe`) or the portable archive (`GeForceNOWRichPresence-Windows.zip`) from the [Releases Page](https://github.com/KarmaDevz/GeForce-NOW-Rich-Presence/releases/latest).
2. Run the installer and launch the app. It will run in your system tray.

### macOS
1. Download the `GeForceNOWRichPresence-macOS.zip` archive.
2. Extract the folder and launch the executable.

### Linux
1. Download the `GeForceNOWRichPresence-Linux.tar.gz` archive.
2. Extract the files, mark the binary as executable (`chmod +x GeForceNOWRichPresence`), and run it.

---

## 💻 Local Compilation & Development

If you want to run the project from source or compile it locally:

### 1. Requirements
* Python 3.12+
* Google Chrome, Microsoft Edge, or a supported browser (for cookies extraction)

### 2. Setup Virtual Environment
```bash
# Clone the repository
git clone https://github.com/KarmaDevz/GeForce-NOW-Rich-Presence.git
cd GeForce-NOW-Rich-Presence

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .\.venv\Scripts\activate

# Install requirements
pip install -r requirements.txt
pip install pyinstaller
```

### 3. Run from Source
```bash
python -m src.GeForceNOWRichPresence
```

### 4. Compile Locally
To compile the standalone package with PyInstaller:
```bash
pyinstaller --clean --noconfirm GeForceNOWRichPresence.spec
```
The compiled output will be generated inside the `dist/GeForceNOWRichPresence/` folder.

---

## 💬 About & Support

Created by [**KarmaDevz**](https://github.com/KarmaDevz) to bridge the gap between cloud gaming and Discord profiles.

⭐️ **Love the project?** Give us a star on GitHub! It helps visibility a lot!

<div align="center">
  <a href="https://github.com/KarmaDevz/GeForce-NOW-Rich-Presence/releases/latest">
    <img src="https://img.shields.io/badge/Download%20Now%20➡️-1B5E20?style=for-the-badge&logo=nvidia&logoColor=white" alt="Download now"/>
  </a>
  <a href="https://paypal.me/KarmaDevz" target="_blank">
    <img src="https://img.shields.io/badge/💖%20Sponsor%20this%20Project-0070ba?style=for-the-badge&logo=paypal&logoColor=white" alt="Paypal Donations">
  </a>
</div>

<br/>

<div align="center">
  <h3>🆘 Need Support?</h3>
  <p>Join the official <strong>GeForce NOW by Digevo</strong> Discord server to get help and chat with the community!</p>
  <a href="https://discord.gg/geforce-now-by-digevo-1412524071878525050">
    <img src="https://img.shields.io/badge/Join%20Discord%20Server-2962FF?style=for-the-badge&logo=discord&logoColor=white" alt="GeForce NOW by Digevo"/>
  </a>
</div>
