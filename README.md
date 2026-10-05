# Notchgent (Dynamic Island HUD for Antigravity)

**Notchgent** is an ultra-lightweight, always-on-top floating "Dynamic Island" widget designed for watching movies, videos, or doing other work while Antigravity agents code in the background.

No more switching back to VS Code or terminals just to press `1`!

---

## ✨ Features

- **Always on Top (HUD)**: Floats gracefully over any fullscreen movie player (VLC, Netflix, YouTube, MPC-HC, Chrome, etc.).
- **Zero Console Clutter**: Launches with `pythonw` with no background cmd window.
- **Dynamic Island States**:
  - **Idle Capsule**: Minimalist pill (`🟢 Notchgent • Idle`) at the top edge of your screen. Doesn't block movie video or subtitles.
  - **Action Needed**: Smoothly springs open when Antigravity asks to edit a file or run a terminal command, displaying the details and action buttons.
  - **🎬 Movie Mode (Auto 15m)**: Tap the `🎬 Auto (15m)` button to auto-approve all agent actions for 15 minutes (with countdown timer) so you can enjoy the movie climax uninterrupted.
- **Global Hotkeys**:
  - <kbd>F8</kbd> : **Approve** (Instantly approves the pending action without touching your mouse or losing video focus).
  - <kbd>F9</kbd> : **Deny** (Rejects the action).
- **Failsafe & Resilient**: If Notchgent is ever closed or offline, Antigravity CLI gracefully falls back to prompting in your VS Code terminal as usual.

---

## 🚀 How to Run

1. Double click **`start.bat`** (or run `pythonw notchgent.py`).
2. The sleek Notch pill will appear at the top-center of your screen.
3. You can click & drag the Notch anywhere if you prefer it in a different position.
4. Open your movie and enjoy! When Antigravity proposes an action:
   - Click **Approve (F8)** on the widget, or
   - Simply tap **F8** on your keyboard from anywhere.

---

## ⚙️ Configuration (`config.json`)

You can edit `config.json` to customize:
- `hotkeys.approve`: Change the approval hotkey (default: `F8`).
- `hotkeys.deny`: Change the denial hotkey (default: `F9`).
- `window.opacity`: Translucency level (default: `0.95`).
- `window.compact_width`: Default compact width (default: `260`).

---

## 🛠️ Antigravity Integration

Installed globally in `~/.gemini/config/hooks.json` using Antigravity's `PreToolUse` lifecycle hook.

To reinstall or uninstall the hook at any time:
- Install: `python install_hook.py`
- Uninstall: `python install_hook.py --uninstall`
