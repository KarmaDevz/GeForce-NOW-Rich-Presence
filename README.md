<div align="center">
  <img src="assets/asset1.jpg" alt="GeForce NOW Rich Presence Banner" width="100%" style="border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.2);" />
  <br/>
  <h1>🎮 GeForce NOW Rich Presence for Discord</h1>
  <p>
    <strong>Display the actual game you are playing on GeForce NOW — automatically, across Windows & Linux.</strong>
  </p>
  
  [🇺🇸 English](./README.md) • [🇪🇸 Español](./README.es.md) • [🇹🇷 Türkçe](./README.tr.md)
  
  <br/>
  <br/>

  <a href="https://github.com/Enderjua/GeForce-NOW-Rich-Presence/releases/latest">
    <img src="https://img.shields.io/github/v/release/Enderjua/GeForce-NOW-Rich-Presence?style=for-the-badge&color=00C853&logo=github&label=Latest%20Release" alt="Latest Release"/>
  </a>
  <a href="https://github.com/Enderjua/GeForce-NOW-Rich-Presence/releases">
    <img src="https://img.shields.io/github/downloads/Enderjua/GeForce-NOW-Rich-Presence/total?style=for-the-badge&color=2962FF&logo=github&label=Downloads" alt="Total Downloads"/>
  </a>
  
</div>

---

## 🕹️ What is this?

**GeForce NOW Rich Presence for Discord** lets you display the **actual game you're playing on GeForce NOW** directly on your Discord profile. No more generic "Playing GeForce NOW" statuses! 

This is a modern, feature-packed **fork** that brings complete multi-OS support, native Linux detection, session integration, customizable details, and reward utility tools. Perfect for streamers, gamers, and power users. 🎮💚

---

## ✨ Features & Major Upgrades

* 🐧 **Linux Support (Wayland & X11 Native)** `[New / Linux Added]`
  * Full integration with Linux systems. Features native window-matching using DBus / KDE KWin Scripting API for Wayland, and an automatic fallback to `xdotool` for X11 environments. No Wine or heavy wrappers required.
* 🌐 **Real-time Steam Session Scraping** `[New]`
  * Grabs your live Steam status directly using local browser cookies (fully automated for Edge/Chrome or customizable manually). This lets you display actual rich session details (e.g., *"Currently In-Game | Dota 2"*, active lobbies) in real time.
* 🎁 **Discord Quest Mode (Multi-Presence)** `[New]`
  * Easily unlock Discord Quests! Simulates multiple game instances cleanly in the background (15 minutes active timer limit per game) via temporary isolated processes.
* ✏️ **Fully Customizable Presence Fields** `[New]`
  * Manually customize details (Line 1), state (Line 2), and active party sizes (current/maximum) directly from system tray inputs.
* 🎨 **Dark Gaming UI** `[New]`
  * Clean, dark cybernetic theme across all interactive Qt5 system tray dialogs.
* ⚡ **Automatic WebDriver Helper (Windows)**
  * Self-healing Edge WebDriver checking and updating.
* ✅ **Plug & Play**: Works immediately out of the box.

---

## 📥 Installation & Setup

### 🪟 Windows

1. Download the pre-built installer `.exe` from our [Latest Releases](https://github.com/Enderjua/GeForce-NOW-Rich-Presence/releases/latest).
2. Run the installer and complete the wizard.
3. Launch the application. It will sit quietly in your system tray (taskbar bottom-right).
4. Launch your game on GeForce NOW and see your profile update instantly!

### 🐧 Linux (Ubuntu, Debian, Fedora, Arch, etc.)

Since GFN on Linux runs via browser or Electron launchers, you can easily run this app directly from source:

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Enderjua/GeForce-NOW-Rich-Presence.git
   cd GFN-Rich-Presence
   ```
2. **Create and activate a virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
   *(Note: Ensure you have `xdotool` installed if you are running on an X11 desktop manager).*
4. **Launch the application:**
   ```bash
   PYTHONPATH=. python3 src/GeForceNOWRichPresence.py
   ```
   *(For pure Wayland sessions, the app automatically hooks into KWin/Wayland APIs natively).*

---

## ⚙️ Tray Icon Commands

Right-click the tray icon to manage active presence details:

| Command | Description |
| :--- | :--- |
| 🎮 **Force Game...** | Override automatic detection and select a specific game to display. |
| 🎁 **Discord Quest Mode** | Launch multi-game active instances for reward completion. |
| ✅ **Get Steam Cookie** | Extract browser cookie to fetch live Steam profile session data. |
| 👥 **Set Max Party Size...**| Adjust displayed custom party limits. |
| 🚀 **Open GeForce NOW** | Quickly start the GFN application launcher. |
| 📊 **Sync Games Database** | Trigger down sync with DiscordDetectable app cache. |
| 📝 **Open Logs** | Easily inspect background debug outputs. |
| ❌ **Exit** | Fully terminate the program. |

---

## 🧠 Behind the Scenes

The program acts as a lightweight daemon:
1. **Tracks** active windows (using OS APIs / KWin DBus on Wayland / Win32 APIs on Windows).
2. **Normalizes** game window titles into clean game names.
3. **Pulls** real-time server information or matches names against Discord's application catalog.
4. **Spawns** a local virtual handler executable (isolated inside a temp directory) to register the rich presence directly into Discord's active client.

---

## 🧩 FAQ

**Q: Do I need to be logged into Steam or have Python for Windows?**  
A: No, Windows has a fully self-contained `.exe`. For Steam rich presence (party size/match data), you can grab your local browser cookie via the tray menu.

**Q: Is it safe to use?**  
A: Absolutely. It runs completely locally, does not ask for or store passwords, and works cleanly alongside your official game launchers.

---

## 💬 Authors, Support & Contact

This project is a collaborative effort between:

* 🧑‍💻 **KarmaDevz** - Original creator and core developer of the Windows package.
  * [GitHub Profile](https://github.com/KarmaDevz) • [Paypal Support](https://paypal.me/KarmaDevz)
* 🛠️ **Enderjua** - Fork maintainer, Linux native integration, Quest Mode implementation, and feature upgrades.
  * **GitHub Fork:** [Enderjua/GeForce-NOW-Rich-Presence](https://github.com/Enderjua/GeForce-NOW-Rich-Presence)
  * **Discord Server:** [Join our Support Discord](https://discord.gg/A9ESFRTzqR)
  * **Email:** enderjua@gmail.com
  * **Instagram:** [@marijuabakunin](https://instagram.com/marijuabakunin)

---

<div align="center">
  <a href="https://github.com/Enderjua/GeForce-NOW-Rich-Presence/releases/latest">
    <img src="https://img.shields.io/badge/Download%20Now%20➡️-1B5E20?style=for-the-badge&logo=nvidia&logoColor=white" alt="Download now"/>
  </a>
</div>
