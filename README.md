# 🔐 Keyzerchief

[![Tests](https://github.com/pedrocatalao/keyzerchief/actions/workflows/tests.yml/badge.svg)](https://github.com/pedrocatalao/keyzerchief/actions/workflows/tests.yml)

Keyzerchief is a terminal user interface (TUI) for exploring and managing Java keystores with a dash of style. It wraps the familiar `keytool` utility in a colorful curses experience so you can inspect entries, import fresh material, or tidy up an aging keystore without ever leaving your keyboard.

> ✨ **Quick glance:** Launch the app, point it at a JKS/PKCS#12 file, and Keyzerchief gives you a dual-pane view with rich shortcuts, contextual menus, and helpful highlighting for expired certificates.

## Table of contents
- [Features](#features)
- [Architecture at a glance](#architecture-at-a-glance)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Usage](#usage)
- [Build & distribution](#build--distribution)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

## Features
- 🎛️ **Dual-pane navigation** to browse aliases on the left and certificate details on the right.
- 🔁 **Tab switching** and subtle dimming that keep you oriented as you move between panes.
- ⌨️ **Keyboard-first controls** with shortcuts for jumping to the top/bottom, filtering, searching, and triggering menu actions.
- 🖱️ **Optional mouse support** so you can scroll, click menus, or select text when needed.
- 🛡️ **Certificate insights** that highlight expired entries and surface key metadata immediately.
- 📥 **Import helpers** for certificates and key pairs (PKCS#8, PKCS#12, PVK, OpenSSL) from local files or URLs.
- 🔑 **Password management** including opening password-protected keystores and changing the store password.
- 🧹 **Housekeeping tools** such as deleting entries, saving modifications, and browsing with a built-in file picker.
- 🔔 **Ambient audio cues** (macOS `afplay`) to celebrate key actions—optional but delightful.

## Architecture at a glance
```
keyzerchief/            Entry script (console launcher)
keyzerchief_app/
├── __main__.py         CLI entrypoint and argument parsing
├── app.py              Primary application loop & window management
├── keystore.py         Data access layer wrapping `keytool`
├── keystore_actions.py Mutating keystore commands
├── menu.py, ui/        UI layout, popups, intro animation, etc.
├── audio.py            Non-blocking sound playback helpers
└── sfx/                Optional MP3 sound effects
```
Everything is written with the Python standard library and relies on `curses` for terminal rendering.

## Prerequisites
- 🐍 **Python** 3.10+ (tested on macOS/Linux – `curses` is not bundled on Windows).
- ☕ **Java Runtime** providing the `keytool` CLI (ships with the JDK or some JREs).
- 🔉 **Optional audio** support via `afplay` (macOS). On other platforms audio is silently skipped.
- 🎨 A UTF-8 capable terminal emulator with at least 120×35 characters recommended for the full experience.

## Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/pedrocatalao/keyzerchief.git
   cd keyzerchief
   ```
2. (Recommended) Create and activate a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
3. Install runtime dependencies (standard library only, but install `readline`/`curses` if your platform requires extra packages).
4. Ensure the `keytool` executable is on your `PATH`:
   ```bash
   keytool -help
   ```

## Usage
Launch Keyzerchief from the project root with either command:
```bash
./keyzerchief            # Direct launcher script (make sure it is executable)
python -m keyzerchief_app  # Module invocation
```

### Opening a keystore
- Provide a keystore path as an argument: `./keyzerchief ~/certs/server.jks`
- Or choose **File → Open** inside the TUI to browse with the built-in picker.

### Navigation cheat-sheet
| Action | Shortcut |
|--------|----------|
| Switch pane | `Tab`
| Scroll list/detail | Arrow keys, `PageUp`, `PageDown`
| Jump to top/bottom | `t` / `b`
| Filter aliases | `/` and start typing
| Search details pane | `Ctrl+f`
| Toggle mouse support | `Ctrl+m`
| Open command menu | `F10` or mouse click on menu bar
| Quit | `Ctrl+c` or menu option

Contextual menus expose imports, password changes, deletion, saving, and more. Expired certificates glow red so you can spot them at a glance.

## Build & distribution
Keyzerchief ships as plain Python. If you want to create a redistributable binary:
1. Install [PyInstaller](https://pyinstaller.org/):
   ```bash
   pip install pyinstaller
   ```
2. Build the executable:
   ```bash
   pyinstaller --name keyzerchief --onefile keyzerchief
   ```
   The resulting binary will live in `dist/keyzerchief`. Ensure it can find `keytool` at runtime.

For packaging to PyPI, add your preferred build backend (`setuptools`, `poetry`, etc.) and wire up the `keyzerchief` console script entry.

## Troubleshooting
- **`keytool: command not found`** – Install a JDK (e.g., [Adoptium Temurin](https://adoptium.net/)) and export its `bin` directory to `PATH`.
- **`_curses` module missing** – On macOS install via `brew install python@3.x`; on Debian/Ubuntu `sudo apt install python3-curses`.
- **Terminal colors look off** – Ensure your terminal supports 256 colors and disable themes that force limited palettes; Make sure you do `export TERM=xterm-256color` in you shell profile.
- **No sound** – Audio cues are macOS-only; other systems skip playback.

## Contributing
Pull requests are welcome! If you add features, please update this README, include relevant screenshots or gifs, and make sure `keytool`-dependent routines handle missing executables gracefully.

## License
This project is released under the [MIT License](LICENSE). 💛
