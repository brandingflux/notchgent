# Notchgent v1.0.1 – Mobile Remote QR Approvals & Dynamic Island HUD

> **Watch movies, streams, and games in fullscreen—or step away from your desk completely while AI agents code in the background.**  
> Review and approve Antigravity CLI / VS Code actions from your desktop or from your phone anywhere in the world.

<p align="center">
  <img src="https://raw.githubusercontent.com/brandingflux/notchgent/main/assets/notchgent-expanded.png" alt="Notchgent Floating Dynamic Island HUD" width="780" />
</p>

| 1. Collapsed Notch | 2. Pending & Countdown | 3. Auto-Executing Dispatch |
| :---: | :---: | :---: |
| <img src="https://raw.githubusercontent.com/brandingflux/notchgent/main/assets/notch-collapsed-closeup.png" alt="Notchgent Collapsed Notch" width="250" /> | <img src="https://raw.githubusercontent.com/brandingflux/notchgent/main/assets/notch-pending-closeup.png" alt="Notchgent Pending Approval" width="250" /> | <img src="https://raw.githubusercontent.com/brandingflux/notchgent/main/assets/notch-auto-action-closeup.png" alt="Notchgent Auto Executing" width="250" /> |
| *Flush top bezel, pulsating orange stroke* | *Live workspace identifier & countdown* | *15ms background auto-dispatch* |

---

## What's New in v1.0.1

### 📱 Mobile Remote Phone Approvals (Anywhere in the World)
- **Zero-Friction Camera QR Pairing**: Click the new `[ 📱 Remote ]` button on the notch to reveal a floating QR code. Scan it with your iPhone or Android camera to immediately pair your device—no mobile app download required!
- **Encrypted Global Access**: Automatic zero-config Cloudflare Quick Tunnel (`trycloudflare.com`) routes approvals directly to your home PC over cellular 4G/5G or remote Wi-Fi, completely bypassing router NAT, firewalls, and CGNAT.
- **Mobile Dynamic Island Web HUD**: Responsive PWA interface styled with Notchgent's signature dark aesthetic, featuring:
  - **Web Audio Chimes**: Synthesized dual-tone alert so you hear approvals even when your phone is resting on a table.
  - **Tactile Haptic Feedback**: Vibrates (`navigator.vibrate`) when approvals arrive and when buttons are pressed.
  - **Live Command & Diff Viewers**: Syntax-highlighted monospace view of the exact bash commands or file patches awaiting review.
  - **Optimistic UI Feedback**: Tapping `[ ✓ Approve ]` instantly dismisses the card and returns to idle with step deduplication to ensure buttons never stick on "Approving...".
  - **Fast Polling Watchdog (750ms)**: Combined with Server-Sent Events (SSE) and anti-buffering headers (`X-Accel-Buffering: no`) so pending actions appear on your phone in under 0.5 seconds without needing manual page refreshes.
- **Windows Power Execution State**: Calls native Win32 `SetThreadExecutionState` to prevent Windows from going to sleep while Notchgent is running, allowing your monitor to turn off while agents continue coding.

---

## Core Highlights (from v1.0.0)

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

### 🎬 Fullscreen Media & Focus Protection
- **Zero Video Interruption**: Approving an action briefly transfers foreground rights in the background for ~15ms via native Win32 `AttachThreadInput`, injects `1` + `Enter`, and **instantly re-pins your media player on top**. VS Code never covers your video.
- **DirectFlip / MPO Bypass**: Bypasses Windows DWM fullscreen suppression by continually asserting `HWND_TOPMOST` with `SWP_NOACTIVATE`.
- **Dynamic Multi-Workspace Routing**: If multiple VS Code windows are open across different repositories, Notchgent inspects the pending tool call's working directory (`Cwd`) and target files to route keystrokes to the exact workspace where the agent is active.

### ⌨️ Universal Controls & Hotkeys
| Action | HUD Control | Global Hotkeys / Mobile |
| :--- | :--- | :--- |
| **Approve Action** | Click `[ ✓ 1. Approve (Alt+1) ]` | <kbd>Alt</kbd>+<kbd>1</kbd>, <kbd>Alt</kbd>+<kbd>A</kbd>, <kbd>F8</kbd> / Phone `[ ✓ Approve ]` |
| **Reject Action** | Click `[ ✕ 2 (Alt+2) ]` | <kbd>Alt</kbd>+<kbd>2</kbd>, <kbd>Alt</kbd>+<kbd>D</kbd>, <kbd>F9</kbd> / Phone `[ ✕ Reject ]` |
| **Toggle Auto Mode** | Click `[ 🎬 Auto ]` / `[ 🎬 14:59 ]` | Click button on capsule / Phone `[ 🎬 Auto ]` |
| **Mobile Remote QR** | Click `[ 📱 Remote ]` | Scan QR code on phone camera |
| **Move Notch** | Drag anywhere inside the capsule | Mouse drag |
| **Close HUD** | Click `[ ✕ ]` | Click button on capsule |

---

## Downloads & Assets

| File | Description | Architecture | Size |
| :--- | :--- | :--- | :--- |
| **[`Notchgent.exe`](dist/Notchgent.exe)** | Standalone portable executable (Zero dependencies, Python runtime & tunnel bundled) | x86_64 / ARM64 (Emulated) | ~117 MB |
| **Source Code (`.zip` / `.tar.gz`)** | Full Python 3 source code with PyQt6, Win32 scripts & Remote PWA | Any | — |

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

---

## Quick Start

1. Download or launch **[`Notchgent.exe`](dist/Notchgent.exe)**.
2. The notch will appear docked at the top center of your screen: `🟢 Notchgent • Idle`.
3. Click **`[ 📱 Remote ]`**, scan the QR code with your phone camera, and pair your phone in seconds.
4. Go about your day—watch movies, step away, or leave the house. Whenever your agent requests approval, review and approve with 1 tap!
