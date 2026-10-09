# Changelog

All notable changes to **Notchgent** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [v1.0.1] - 2026-10-09

### 📱 Added
- **Mobile Remote Phone Approvals**:
  - Developers can now scan a dynamic QR code on their monitor and approve Antigravity CLI actions from anywhere in the world (over cellular 4G/5G or local Wi-Fi) while their PC remains running at home.
  - **Embedded HTTP & SSE Server (`remote_server.py`)**: Runs an asynchronous micro-server on port 5151 serving a dark-mode mobile web application with sub-second Server-Sent Events (SSE) and an active 750ms fast-polling watchdog.
  - **Zero-Config Cloudflare Quick Tunnel (`tunnel_manager.py`)**: Automatically manages `cloudflared.exe` to provision instant, encrypted public HTTPS access (`*.trycloudflare.com`) with zero accounts, zero API keys, and zero router port-forwarding required.
  - **QR Pairing Modal (`remote_dialog.py`)**: Integrated flyout card on the desktop HUD showing the live high-resolution QR code, one-click "Copy Link" button, and "Rotate Key" button for immediate session revocation.
  - **Mobile Dynamic Island Web App**: Dark glass aesthetic styled to match Notchgent, featuring Web Audio alert chimes, tactile haptic vibration (`navigator.vibrate`), live command and diff viewers, and responsive thumb buttons.
  - **Optimistic UI Feedback**: Instant checkmark transition on phone upon approval tap with step deduplication to guarantee buttons never stick or hang.
  - **Windows Power Management (`SetThreadExecutionState`)**: Keeps Windows in an active execution state while remote mode is active, allowing displays to sleep while preventing PC suspension during autonomous coding tasks.
- **Pixel-Crisp Vector SVG Icon Engine (`icons.py`)**:
  - Replaced all system emojis across the entire application with dedicated vector SVG icons (`phone`, `clapperboard`, `terminal`, `file_edit`, `file_plus`, `help_circle`, `check`, `x`, `copy`, `rotate`, `wifi`, `zap`, `shield_check`, `globe`).
  - Resolution-independent rendering rendered at 2x High-DPI scale for sharp lines on 4K/retina monitors and mobile OLED screens.
  - Inline vector SVG injection in the mobile PWA with zero external asset dependencies.
- **Self-Healing Tunnel Supervisor & Edge Watchdog (`tunnel_manager.py`)**:
  - Replaced one-shot process execution with a continuous background supervisor loop that prevents tunnels from dying after prolonged hours of operation.
  - Added an active edge heartbeat probe every 30 seconds that detects silent Cloudflare edge drops or DNS expirations and automatically re-provisions a fresh tunnel.
  - Added dedicated `restart()` trigger wired directly to the modal's "Rotate & Refresh" button for instant on-demand link regeneration.
  - Added support for permanent named Cloudflare Tunnels via `config.json` (`tunnel_token`, `tunnel_url`).
- **Dual-Mode Network Switcher (`remote_dialog.py`)**:
  - Added segmented switcher tabs between **Public (5G / Remote)** and **Home Wi-Fi (Direct LAN)**.
  - Users on home Wi-Fi can now connect directly with 0ms cloud lag, zero Cloudflare dependencies, and infinite uptime.


### 🛠️ Changed
- **HUD Interface**: Replaced unicode emojis on header buttons (`Remote`, `Auto`, `Close`), action buttons (`Approve`, `Reject`), and tool badge headers (`Shell Command`, `Edit File`, `Create File`, `Question`) with vector SVG icons.
- **Dynamic Connection Badge**: Button dynamically displays active mobile connection counts (e.g. `1 Online`) with emerald green SVG indicator.
- **Build System**: Updated `Notchgent.spec` and `build.bat` to bundle `icons.py`, `PyQt6.QtSvg`, `cloudflared.exe`, `qrcode`, and all remote networking modules into the standalone single-file binary.
- **Process Management**: Improved `build.bat` to terminate lingering instances before building, preventing `PermissionError [WinError 5]`.

---

## [v1.0.0] - 2026-10-08

### 🚀 Initial Release
- **Always-on-Top Hardware Notch Geometry**: Anchored flush to the top bezel (`y = 0`) with sharp top corners and smooth 20px rounded bottom corners.
- **Apple Dynamic Island Spring Physics**: Fluid spring bounce transitions powered by `QPropertyAnimation` (`OutBack` expand, `OutCubic` collapse).
- **Fullscreen Media & Focus Protection**: 15ms background keystroke injection via native Win32 `AttachThreadInput` + `HWND_TOPMOST` persistence over fullscreen video players (VLC, Media Player, Netflix, Chrome).
- **Dynamic Multi-Workspace Routing**: Intelligent targeting of the active VS Code window based on tool call working directory (`Cwd`) and project paths.
- **15-Minute Auto Mode**: Optional hands-free timer with signature breathing orange border pulsation (`#f97316`).
- **Universal Global Hotkeys**: Quick approvals with <kbd>Alt</kbd>+<kbd>1</kbd> / <kbd>Alt</kbd>+<kbd>A</kbd> / <kbd>F8</kbd> and rejections with <kbd>Alt</kbd>+<kbd>2</kbd> / <kbd>Alt</kbd>+<kbd>D</kbd> / <kbd>F9</kbd>.
