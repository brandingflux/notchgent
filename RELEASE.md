# Notchgent v1.0.0 – True Dynamic Island HUD for Antigravity & VS Code

> **Watch movies, streams, and games in fullscreen while AI agents code in the background.**  
> Review and approve Antigravity CLI / VS Code actions with 1 click or a global hotkey—**without Alt-Tabbing, without window popups, and without interrupting your video.**

<p align="center">
  <img src="https://raw.githubusercontent.com/brandingflux/notchgent/main/assets/notchgent-expanded.png" alt="Notchgent Floating Dynamic Island HUD" width="780" />
</p>

| 1. Collapsed Notch | 2. Pending & Countdown | 3. Auto-Executing Dispatch |
| :---: | :---: | :---: |
| <img src="https://raw.githubusercontent.com/brandingflux/notchgent/main/assets/notch-collapsed-closeup.png" alt="Notchgent Collapsed Notch" width="250" /> | <img src="https://raw.githubusercontent.com/brandingflux/notchgent/main/assets/notch-pending-closeup.png" alt="Notchgent Pending Approval" width="250" /> | <img src="https://raw.githubusercontent.com/brandingflux/notchgent/main/assets/notch-auto-action-closeup.png" alt="Notchgent Auto Executing" width="250" /> |
| *Flush top bezel, pulsating orange stroke* | *Live workspace identifier & countdown* | *15ms background auto-dispatch* |

---

## What's New in v1.0.0

### 🏝️ True Screen Notch Geometry
- **Top Bezel Flush**: Anchored directly to the very top edge of your screen (`y = 0`) to look and feel like an authentic hardware notch.
- **Asymmetric Corner Radii**: Sharp 0px top corners merge seamlessly into the monitor bezel, while bottom corners curve gently with a smooth 20px radius.
- **Zero-Artifact Translucency**: Native DWM borderless rendering with per-pixel 32-bit ARGB alpha transparency eliminates ugly rectangular window bounding boxes.

### 🍏 Apple Dynamic Island Spring Fluid Animations
- **Physical Spring Physics**: Window geometry transitions use `QPropertyAnimation` with an organic `QEasingCurve.Type.OutBack` easing curve that gently overshoots and settles on expand.
- **Snap Collapse**: Collapses back to the compact 48px capsule using `QEasingCurve.Type.OutCubic` when actions are executed or dismissed.

### 🧡 Signature Orange Border & Breathing Auto-Pulse
- **Vibrant Orange Border**: Framed by a distinct 1.5px orange stroke (`#f97316`) on the sides and bottom, leaving the top flush with your screen bezel.
- **Smooth 25fps Breathing Pulse**: When **🎬 Auto Mode** is engaged, the border smoothly oscillates its opacity and thickness in an organic breathing rhythm.
- **Cohesive Auto Theme**: The `🎬 Auto` toggle button and status dot switch to active orange while the timer is running.

### 🎬 Fullscreen Media & Focus Protection
- **Zero Video Interruption**: Approving an action briefly transfers foreground rights in the background for ~15ms via native Win32 `AttachThreadInput`, injects `1` + `Enter`, and **instantly re-pins your media player on top**. VS Code never covers your video.
- **DirectFlip / MPO Bypass**: Bypasses Windows DWM fullscreen suppression by continually asserting `HWND_TOPMOST` with `SWP_NOACTIVATE`.
- **Dynamic Multi-Workspace Routing**: If multiple VS Code windows are open across different repositories, Notchgent inspects the pending tool call's working directory (`Cwd`) and target files to route keystrokes to the exact workspace where the agent is active.
- **Auto Re-minimization**: If VS Code was minimized to the taskbar, it receives the approval keystroke and is immediately tucked back into the taskbar (`SW_MINIMIZE`).

### ⌨️ Universal Global Hotkeys
| Action | HUD Button | Global Hotkeys |
| :--- | :--- | :--- |
| **Approve Action** | `[ ✓ 1. Approve (Alt+1) ]` | <kbd>Alt</kbd>+<kbd>1</kbd>, <kbd>Alt</kbd>+<kbd>A</kbd>, <kbd>F8</kbd> |
| **Reject Action** | `[ ✕ 2 (Alt+2) ]` | <kbd>Alt</kbd>+<kbd>2</kbd>, <kbd>Alt</kbd>+<kbd>D</kbd>, <kbd>F9</kbd> |
| **Toggle Auto Mode** | `[ 🎬 Auto ]` / `[ 🎬 14:59 ]` | Click button on capsule |
| **Move Notch** | Drag anywhere inside the capsule | Mouse drag |
| **Close HUD** | `[ ✕ ]` | Click button on capsule |

---

## Downloads & Assets

| File | Description | Architecture | Size |
| :--- | :--- | :--- | :--- |
| **[`Notchgent.exe`](dist/Notchgent.exe)** | Standalone portable executable (Zero dependencies, Python runtime bundled) | x86_64 / ARM64 (Emulated) | ~99.6 MB |
| **Source Code (`.zip` / `.tar.gz`)** | Full Python 3 source code with PyQt6 & Win32 scripts | Any | — |

---

## System Requirements & Compatibility

### Architecture Support
- **x86_64 / AMD64 (64-bit)**: Native execution on modern Intel and AMD processors.
- **ARM64 (Windows on ARM)**: Supported on Windows 11 ARM64 devices (Surface Pro, Snapdragon X Elite / Copilot+ PCs) via Microsoft Prism x64 emulation.
- **x86 (32-bit Legacy)**: Not supported.

### Operating Systems
- **Windows 11 (64-bit)**: Optimal / Recommended (supports modern DWM borderless compositing).
- **Windows 10 (64-bit, version 1809+)**: Supported.
- **macOS / Linux**: Not supported (relies deeply on Win32 `user32.dll`, `dwmapi.dll`, and `HWND_TOPMOST` mechanics).

### Prerequisites
- **No Python Required**: The standalone `Notchgent.exe` comes pre-packaged with Python 3.13, PyQt6, Qt6 libraries, and PyWin32 DLLs.
- **Visual C++ Runtime**: Standard `Microsoft Visual C++ Redistributable 2015–2022 (x64)` (pre-installed on virtually all Windows systems).
- **Antigravity CLI / IDE**: Antigravity sessions must be active so the transcript log `~/.gemini/antigravity-cli/brain/<conversation-id>/.../transcript.jsonl` exists for Notchgent to monitor.

---

## Quick Start

1. Download **[`Notchgent.exe`](dist/Notchgent.exe)**.
2. Double-click to launch. The notch will appear docked at the top center of your screen: `🟢 Notchgent • Idle`.
3. Open a movie or video in fullscreen (VLC, Media Player, Netflix, YouTube, etc.).
4. Start an Antigravity task in VS Code or CLI (`agy`).
5. When the agent requests tool approval:
   - The notch springs open with an alert chime.
   - Shows the command or file edit details and workspace name.
   - Press <kbd>Alt</kbd>+<kbd>1</kbd> (or click **Approve**) to approve without losing fullscreen focus!
6. Click **🎬 Auto** to enable the 15-minute hands-free countdown with breathing orange pulsation.

---

## Security & Permissions Notice

- **Standard User Privileges**: Notchgent runs with standard user permissions.
- **Elevated VS Code**: If your VS Code or terminal is running *"As Administrator"*, Windows UIPI (User Interface Privilege Isolation) blocks keystrokes from standard processes. In that case, launch `Notchgent.exe` as Administrator as well.
- **Windows Defender SmartScreen**: Because the executable is built locally and is not signed with a commercial EV certificate, Windows Defender SmartScreen may display *"Unknown Publisher"*. Click **More info** $\rightarrow$ **Run anyway**.
