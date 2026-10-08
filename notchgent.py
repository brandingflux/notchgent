#!/usr/bin/env python3
"""
Notchgent - Floating Live HUD for Antigravity & VS Code.
Automatically monitors Antigravity's live transcript log in real time.
When an action is proposed:
  - Plays a gentle alert chime
  - Springs open to display the exact command or file edit details
  - Lets you approve with 1-click or Alt+1/Alt+A hotkey (sending '1' + Enter to VS Code)
  - Automatically collapses back to the minimal idle capsule once executed!
"""

import sys
import os
import glob
import json
import time
import math
import threading
from typing import Optional, Tuple, Dict, Any, List

# Ensure High DPI awareness
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

from PyQt6.QtCore import (
    Qt, QPoint, QRect, pyqtSignal, QObject, QTimer,
    QPropertyAnimation, QEasingCurve
)
from PyQt6.QtGui import (
    QColor, QFont, QIcon
)
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QGraphicsDropShadowEffect, QFrame, QTextEdit
)

import win32gui
import win32process
import win32con
import win32api
import ctypes
import psutil
import pyautogui

try:
    from pynput import keyboard
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False


if getattr(sys, "frozen", False):
    SCRIPT_DIR = os.path.dirname(sys.executable)
else:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PID_FILE = os.path.join(SCRIPT_DIR, ".notchgent.pid")
BRAIN_DIR = os.path.expanduser("~/.gemini/antigravity-cli/brain")


def kill_previous_instance():
    """Kill any previously running notchgent instance using PID file."""
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, "r") as f:
                old_pid = int(f.read().strip())
            if old_pid != os.getpid():
                import subprocess
                subprocess.run(["taskkill", "/F", "/PID", str(old_pid)], capture_output=True)
        except Exception:
            pass
    try:
        with open(PID_FILE, "w") as f:
            f.write(str(os.getpid()))
    except Exception:
        pass


def ensure_default_desktop():
    """Ensure the current thread is attached to the interactive 'default' desktop."""
    try:
        u = ctypes.windll.user32
        d = u.OpenDesktopW("default", 0, False, 0x01FF)
        if d:
            u.SetThreadDesktop(d)
    except Exception:
        pass


def find_vscode_window(workspace_hints: Optional[List[str]] = None) -> Tuple[Optional[int], str]:
    """Find the matching VS Code window handle for the given workspace, or the MRU VS Code window."""
    ensure_default_desktop()
    candidates = []

    # Get windows in exact Z-order (MRU order)
    top_hwnd = win32gui.GetTopWindow(win32gui.GetDesktopWindow())
    z_index = 0
    while top_hwnd:
        try:
            if win32gui.IsWindowVisible(top_hwnd) or win32gui.IsIconic(top_hwnd):
                title = win32gui.GetWindowText(top_hwnd)
                _, pid = win32process.GetWindowThreadProcessId(top_hwnd)
                proc = psutil.Process(pid)
                pname = proc.name().lower()
                if "code" in pname and title and "visual studio code" in title.lower():
                    rect = win32gui.GetWindowRect(top_hwnd)
                    width = rect[2] - rect[0]
                    height = rect[3] - rect[1]
                    if (width > 400 and height > 250) or win32gui.IsIconic(top_hwnd):
                        candidates.append((top_hwnd, title, z_index))
        except Exception:
            pass
        top_hwnd = win32gui.GetWindow(top_hwnd, win32con.GW_HWNDNEXT)
        z_index += 1

    if not candidates:
        return None, ""

    # 1. Match candidates against workspace hints (e.g. TTS, notchgent, FFTL-light-astro-theme)
    if workspace_hints:
        hints = [workspace_hints] if isinstance(workspace_hints, str) else list(workspace_hints)
        for h in hints:
            h_clean = h.lower().strip()
            if not h_clean or len(h_clean) < 2:
                continue
            for hwnd, title, z in candidates:
                t_lower = title.lower()
                # Check for workspace word in VS Code title
                if f"- {h_clean} -" in t_lower or f" {h_clean} " in t_lower or h_clean in t_lower:
                    return hwnd, title

    # 2. Fallback: Return the most recently active VS Code window (top of OS Z-order)
    candidates.sort(key=lambda x: x[2])
    return candidates[0][0], candidates[0][1]


def force_foreground_window(hwnd: int) -> bool:
    """Robustly brings hwnd to foreground without stealing focus to menu bar."""
    if not hwnd or not win32gui.IsWindow(hwnd):
        return False
    if win32gui.GetForegroundWindow() == hwnd:
        return True

    try:
        ctypes.windll.user32.AllowSetForegroundWindow(-1)
        ctypes.windll.user32.LockSetForegroundWindow(2)  # LSFW_UNLOCK

        fg = win32gui.GetForegroundWindow()
        if fg and win32gui.IsWindow(fg) and fg != hwnd:
            fg_thread = win32process.GetWindowThreadProcessId(fg)[0]
            target_thread = win32process.GetWindowThreadProcessId(hwnd)[0]
            my_thread = win32api.GetCurrentThreadId()

            try:
                win32process.AttachThreadInput(my_thread, fg_thread, True)
                win32process.AttachThreadInput(my_thread, target_thread, True)
                win32gui.BringWindowToTop(hwnd)
                win32gui.SetForegroundWindow(hwnd)
                win32process.AttachThreadInput(my_thread, target_thread, False)
                win32process.AttachThreadInput(my_thread, fg_thread, False)
            except Exception:
                pass

        if win32gui.GetForegroundWindow() != hwnd:
            # Fallback: Alt key down across activation, then dismiss any menu focus with Ctrl tap
            win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)
            win32gui.BringWindowToTop(hwnd)
            win32gui.SetForegroundWindow(hwnd)
            win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)
            time.sleep(0.01)
            win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
            win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)
    except Exception:
        pass

    return win32gui.GetForegroundWindow() == hwnd


def send_key_to_vscode(
    key_text: str = "1",
    movie_hwnd: Optional[int] = None,
    notch_hwnd: Optional[int] = None,
    workspace_hints: Optional[List[str]] = None
) -> bool:
    """Send '1' or '2' + Enter to VS Code, occluded behind the user's movie player if active."""
    ensure_default_desktop()
    target_hwnd, title = find_vscode_window(workspace_hints)
    if not target_hwnd:
        return False

    was_minimized = win32gui.IsIconic(target_hwnd)

    # Only treat as a movie window if it is an existing, visible window with a title, distinct from VS Code
    has_movie = bool(
        movie_hwnd
        and win32gui.IsWindow(movie_hwnd)
        and movie_hwnd != target_hwnd
        and win32gui.GetWindowText(movie_hwnd).strip()
    )

    was_movie_topmost = False

    try:
        if has_movie:
            # 1. Shield: Pin movie window topmost so VS Code cannot flash over it
            try:
                ex_style = win32gui.GetWindowLong(movie_hwnd, win32con.GWL_EXSTYLE)
                was_movie_topmost = bool(ex_style & win32con.WS_EX_TOPMOST)
                win32gui.SetWindowPos(
                    movie_hwnd, win32con.HWND_TOPMOST,
                    0, 0, 0, 0,
                    win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE
                )
            except Exception:
                pass

            # 2. Keep Notchgent HUD above the movie window
            if notch_hwnd and win32gui.IsWindow(notch_hwnd):
                try:
                    win32gui.SetWindowPos(
                        notch_hwnd, win32con.HWND_TOPMOST,
                        0, 0, 0, 0,
                        win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE | win32con.SWP_SHOWWINDOW
                    )
                except Exception:
                    pass

            # 3. Ensure VS Code is strictly in the standard (non-topmost) Z-band
            try:
                win32gui.SetWindowPos(
                    target_hwnd, win32con.HWND_NOTOPMOST,
                    0, 0, 0, 0,
                    win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE
                )
            except Exception:
                pass

        if was_minimized:
            win32gui.ShowWindow(target_hwnd, win32con.SW_RESTORE)
            time.sleep(0.04)

        # 4. Focus VS Code
        for _ in range(3):
            if force_foreground_window(target_hwnd):
                break
            time.sleep(0.02)

        time.sleep(0.03)

        # 5. Send keystroke + enter
        vk = ord(key_text[0].upper()) if key_text else ord('1')
        win32api.keybd_event(vk, 0, 0, 0)
        win32api.keybd_event(vk, 0, win32con.KEYEVENTF_KEYUP, 0)
        time.sleep(0.02)
        win32api.keybd_event(win32con.VK_RETURN, 0, 0, 0)
        win32api.keybd_event(win32con.VK_RETURN, 0, win32con.KEYEVENTF_KEYUP, 0)
        time.sleep(0.04)

    except Exception:
        return False
    finally:
        # 1. If VS Code was minimized before, re-minimize it immediately
        if was_minimized:
            try:
                win32gui.ShowWindow(target_hwnd, win32con.SW_MINIMIZE)
            except Exception:
                pass

        # 2. Restore foreground focus to the user's movie player if one was active
        if has_movie:
            try:
                force_foreground_window(movie_hwnd)
                if not was_movie_topmost:
                    win32gui.SetWindowPos(
                        movie_hwnd, win32con.HWND_NOTOPMOST,
                        0, 0, 0, 0,
                        win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE
                    )
            except Exception:
                pass

        # 3. Always re-assert Notchgent HUD at the absolute top of the HWND_TOPMOST layer
        if notch_hwnd and win32gui.IsWindow(notch_hwnd):
            try:
                win32gui.SetWindowPos(
                    notch_hwnd, win32con.HWND_TOPMOST,
                    0, 0, 0, 0,
                    win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE | win32con.SWP_SHOWWINDOW
                )
            except Exception:
                pass

    return True


def get_latest_transcript_file() -> Optional[str]:
    """Find the most recently modified transcript.jsonl file."""
    pattern = os.path.join(BRAIN_DIR, "*", ".system_generated", "logs", "transcript.jsonl")
    files = glob.glob(pattern)
    if not files:
        return None
    files.sort(key=os.path.getmtime, reverse=True)
    return files[0]


def extract_workspace_hints(args: dict, transcript_file: Optional[str] = None) -> List[str]:
    """Extract candidate workspace/folder names from tool arguments and transcript logs."""
    hints = []
    # 1. From path arguments in the current tool call
    for key in ("Cwd", "TargetFile", "AbsolutePath"):
        raw_path = args.get(key)
        if raw_path and isinstance(raw_path, str):
            clean = raw_path.strip('"\'')
            norm = os.path.normpath(clean)
            parts = [p for p in norm.split(os.sep) if p and not p.endswith(":") and p != "."]
            for part in reversed(parts):
                if len(part) > 1 and part.lower() not in ("src", "app", "components", "lib", "node_modules", "pages", "dist", "build", "public"):
                    if part not in hints:
                        hints.append(part)

    # 2. Search backwards in transcript_file for recent Cwd or TargetFile
    if not hints and transcript_file and os.path.exists(transcript_file):
        try:
            with open(transcript_file, "r", encoding="utf-8", errors="ignore") as f:
                f.seek(0, os.SEEK_END)
                size = f.tell()
                f.seek(max(0, size - 16384))
                lines = [l.strip() for l in f.readlines() if l.strip()]
            for line in reversed(lines):
                if '"Cwd"' in line or '"TargetFile"' in line or '"AbsolutePath"' in line:
                    obj = json.loads(line)
                    for tc in obj.get("tool_calls", []):
                        a = tc.get("args", {})
                        if isinstance(a, str):
                            try:
                                a = json.loads(a)
                            except Exception:
                                pass
                        for k in ("Cwd", "TargetFile", "AbsolutePath"):
                            p = a.get(k)
                            if p and isinstance(p, str):
                                norm = os.path.normpath(p.strip('"\''))
                                parts = [x for x in norm.split(os.sep) if x and not x.endswith(":") and x != "."]
                                for part in reversed(parts):
                                    if len(part) > 1 and part.lower() not in ("src", "app", "components", "lib", "node_modules"):
                                        if part not in hints:
                                            hints.append(part)
                    if hints:
                        break
        except Exception:
            pass

    # 3. Add active agy.exe workspace names
    try:
        for p in psutil.process_iter(['pid', 'name']):
            if 'agy' in p.info['name'].lower():
                env = p.environ()
                ws = env.get('GEMINI_CLI_IDE_WORKSPACE_PATH') or p.cwd()
                if ws:
                    folder = os.path.basename(os.path.normpath(ws))
                    if folder and folder not in hints:
                        hints.append(folder)
    except Exception:
        pass

    return hints


class TranscriptWatcher(QObject):
    action_pending = pyqtSignal(dict)  # Emitted when an action is awaiting approval
    action_cleared = pyqtSignal()      # Emitted when agent is idle or finished

    def __init__(self):
        super().__init__()
        self.last_step_index = -1
        self.currently_pending = False
        self.last_file: Optional[str] = None
        self.file_pos = 0

    def check_for_updates(self):
        transcript_file = get_latest_transcript_file()
        if not transcript_file or not os.path.exists(transcript_file):
            return

        try:
            # Read the last few non-empty lines
            with open(transcript_file, "r", encoding="utf-8", errors="ignore") as f:
                # Seek near the end for performance
                f.seek(0, os.SEEK_END)
                size = f.tell()
                read_size = min(size, 8192)
                f.seek(size - read_size)
                lines = [l.strip() for l in f.readlines() if l.strip()]

            if not lines:
                return

            last_obj = json.loads(lines[-1])
            step_idx = last_obj.get("step_index", 0)
            step_type = last_obj.get("type", "")

            # If the last entry is PLANNER_RESPONSE with tool_calls, a tool is awaiting approval!
            if step_type == "PLANNER_RESPONSE" and last_obj.get("tool_calls"):
                tool_call = last_obj["tool_calls"][0]
                tool_name = tool_call.get("name", "Tool")
                args = tool_call.get("args", {})

                # If args were stringified JSON, parse them
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        args = {"raw": args}

                # Extract workspace hints dynamically
                workspace_hints = extract_workspace_hints(args, transcript_file)

                # Only notify if this is a newly observed pending step
                if not self.currently_pending or step_idx != self.last_step_index:
                    self.currently_pending = True
                    self.last_step_index = step_idx
                    self.action_pending.emit({
                        "step_index": step_idx,
                        "tool_name": tool_name,
                        "args": args,
                        "workspace_hints": workspace_hints
                    })

            # If the last entry is GENERIC, USER_INPUT, or SYSTEM_MESSAGE, the tool execution finished!
            elif step_type in ("GENERIC", "USER_INPUT", "SYSTEM_MESSAGE") or (step_type == "PLANNER_RESPONSE" and not last_obj.get("tool_calls")):
                if self.currently_pending:
                    self.currently_pending = False
                    self.action_cleared.emit()

        except Exception:
            pass


class NotchgentHUD(QWidget):
    key_sent_signal = pyqtSignal(bool, str)

    def __init__(self):
        super().__init__()
        self.key_sent_signal.connect(self._on_key_sent)
        self.is_expanded = False
        self.drag_pos = QPoint()
        self.auto_movie_active = False
        self.auto_countdown = 0
        self.last_chime_step = -1
        self.last_user_hwnd = None
        self.pending_movie_hwnd = None
        self.current_workspace_hints: List[str] = []
        self.pinned_y = 0
        self.pinned_center_x = None

        # Pulsation for Auto Movie Mode
        self.pulse_phase = 0.0
        self.pulse_timer = QTimer(self)
        self.pulse_timer.setInterval(40)
        self.pulse_timer.timeout.connect(self._on_pulse_tick)
        self.frame_shadow: Optional[QGraphicsDropShadowEffect] = None

        self.sound_mode = "beep"
        config_path = os.path.join(SCRIPT_DIR, "config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    self.sound_mode = str(cfg.get("sound", "beep")).lower()
            except Exception:
                pass

        self.setup_ui()
        self.setup_watcher()
        self.setup_hotkeys()

    def setup_ui(self):
        self.setObjectName("NotchgentHUD")

        # Window Flags: Always on Top, Frameless, Tool Window
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowOpacity(1.0)
        self.setMinimumSize(300, 40)
        self.setMaximumSize(650, 320)

        # Outer Layout (0px margins: frame exactly matches window, eliminating any negative layered window bounding box)
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Main Capsule Frame
        self.frame = QFrame(self)
        self.frame.setObjectName("MainFrame")
        self.frame_layout = QVBoxLayout(self.frame)
        self.frame_layout.setContentsMargins(16, 7, 16, 7)
        self.frame_layout.setSpacing(8)
        self.frame_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # --- Compact Header Bar (Always visible) ---
        self.header_widget = QWidget()
        self.header_widget.setFixedHeight(26)
        self.header_layout = QHBoxLayout(self.header_widget)
        self.header_layout.setContentsMargins(0, 0, 0, 0)
        self.header_layout.setSpacing(8)
        self.header_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.status_dot = QLabel("●")
        self.status_dot.setObjectName("StatusDot")
        self.status_dot.setFixedWidth(14)

        self.status_label = QLabel("Notchgent • Idle")
        self.status_label.setObjectName("StatusLabel")
        font = QFont("Segoe UI", 10, QFont.Weight.DemiBold)
        self.status_label.setFont(font)
        self.status_label.setMinimumWidth(140)

        self.movie_mode_btn = QPushButton("🎬 Auto")
        self.movie_mode_btn.setObjectName("MovieModeBtn")
        self.movie_mode_btn.setCheckable(True)
        self.movie_mode_btn.setFixedSize(84, 24)
        self.movie_mode_btn.clicked.connect(self.toggle_movie_mode)

        self.close_btn = QPushButton("✕")
        self.close_btn.setObjectName("CloseBtn")
        self.close_btn.setFixedSize(20, 20)
        self.close_btn.clicked.connect(self.close)

        self.header_layout.addWidget(self.status_dot)
        self.header_layout.addWidget(self.status_label, 1)
        self.header_layout.addWidget(self.movie_mode_btn)
        self.header_layout.addWidget(self.close_btn)

        self.frame_layout.addWidget(self.header_widget)

        # --- Expanded Content Section (Visible when action pending) ---
        self.expanded_widget = QWidget()
        self.expanded_layout = QVBoxLayout(self.expanded_widget)
        self.expanded_layout.setContentsMargins(0, 6, 0, 0)
        self.expanded_layout.setSpacing(8)

        # Badge
        self.tool_badge = QLabel("⚡ Tool Execution")
        self.tool_badge.setObjectName("ToolBadge")
        self.expanded_layout.addWidget(self.tool_badge)

        # Details Box
        self.details_box = QTextEdit()
        self.details_box.setObjectName("DetailsBox")
        self.details_box.setReadOnly(True)
        self.details_box.setFixedHeight(75)
        self.expanded_layout.addWidget(self.details_box)

        # Buttons Row: [ ✓ 1. Approve (Alt+1) ] [ ✕ 2. Reject (Alt+2) ]
        self.btn_layout = QHBoxLayout()
        self.btn_layout.setSpacing(8)

        self.approve_btn = QPushButton("✓ 1. Approve (Alt+1)")
        self.approve_btn.setObjectName("ApproveBtn")
        self.approve_btn.setFixedHeight(34)
        self.approve_btn.clicked.connect(self.on_approve_clicked)

        self.deny_btn = QPushButton("✕ 2 (Alt+2)")
        self.deny_btn.setObjectName("DenyBtn")
        self.deny_btn.setFixedHeight(34)
        self.deny_btn.clicked.connect(self.on_deny_clicked)

        self.btn_layout.addWidget(self.approve_btn, 2)
        self.btn_layout.addWidget(self.deny_btn, 1)

        self.expanded_layout.addLayout(self.btn_layout)
        self.frame_layout.addWidget(self.expanded_widget)

        self.main_layout.addWidget(self.frame)

        # Stylesheet
        self.setStyleSheet("""
            QWidget#NotchgentHUD {
                background: transparent;
            }
            QWidget {
                font-family: 'Segoe UI', -apple-system, sans-serif;
            }
            #MainFrame {
                background-color: rgba(18, 20, 26, 0.90);
                border: 1.5px solid rgba(249, 115, 22, 0.90);
                border-top: none;
                border-top-left-radius: 0px;
                border-top-right-radius: 0px;
                border-bottom-left-radius: 20px;
                border-bottom-right-radius: 20px;
            }
            #StatusDot {
                color: #10b981;
                font-size: 13px;
                padding-bottom: 1px;
            }
            #StatusLabel {
                color: #ffffff;
                font-size: 11px;
                font-weight: 600;
            }
            #MovieModeBtn {
                background-color: rgba(255, 255, 255, 0.1);
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 0.18);
                border-radius: 12px;
                font-size: 11px;
                font-weight: 600;
                padding: 0 4px;
            }
            #MovieModeBtn:hover {
                background-color: rgba(255, 255, 255, 0.2);
                color: #ffffff;
            }
            #MovieModeBtn:checked {
                background-color: #ea580c;
                color: #ffffff;
                border: 1px solid #fb923c;
            }
            #CloseBtn {
                background: transparent;
                color: #6b7280;
                border: none;
                font-size: 10px;
                font-weight: bold;
                border-radius: 10px;
            }
            #CloseBtn:hover {
                background-color: rgba(239, 68, 68, 0.3);
                color: #ef4444;
            }
            #ToolBadge {
                background-color: rgba(139, 92, 246, 0.25);
                color: #c4b5fd;
                border: 1px solid rgba(139, 92, 246, 0.45);
                border-radius: 6px;
                padding: 3px 8px;
                font-size: 11px;
                font-weight: 600;
            }
            #DetailsBox {
                background-color: rgba(10, 12, 16, 0.60);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 10px;
                color: #f3f4f6;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 11px;
                padding: 6px;
            }
            #ApproveBtn {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #10b981, stop:1 #059669);
                color: #ffffff;
                font-weight: 700;
                font-size: 12px;
                border: none;
                border-radius: 8px;
            }
            #ApproveBtn:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #34d399, stop:1 #10b981);
            }
            #DenyBtn {
                background-color: rgba(239, 68, 68, 0.18);
                color: #fca5a5;
                font-weight: 700;
                font-size: 12px;
                border: 1px solid rgba(239, 68, 68, 0.35);
                border-radius: 8px;
            }
            #DenyBtn:hover {
                background-color: rgba(239, 68, 68, 0.35);
                color: #ffffff;
            }
        """)

        # Spring fluid animation for Dynamic Island
        self.anim = QPropertyAnimation(self, b"geometry")
        self.anim.finished.connect(self._on_anim_finished)

        self.collapse()

    def showEvent(self, event):
        super().showEvent(event)
        self.apply_glass_effect()

    def apply_glass_effect(self):
        """Configure DWM attributes to eliminate outer window borders and enable dark mode."""
        try:
            hwnd = int(self.winId())
            dwmapi = ctypes.windll.dwmapi
            # Eliminate any DWM system border (DWMWA_BORDER_COLOR = 34, 0xFFFFFFFE = DWMWA_COLOR_NONE)
            border_none = ctypes.c_uint(0xFFFFFFFE)
            dwmapi.DwmSetWindowAttribute(hwnd, 34, ctypes.byref(border_none), ctypes.sizeof(border_none))
            # Set dark mode attribute (DWMWA_USE_IMMERSIVE_DARK_MODE = 20)
            dark = ctypes.c_int(1)
            dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(dark), ctypes.sizeof(dark))
        except Exception:
            pass

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Only drag if clicking inside the visible capsule frame
            if not self.frame.geometry().contains(event.position().toPoint()):
                event.ignore()
                return
            self.drag_pos = event.globalPosition().toPoint() - self.pos()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and not self.drag_pos.isNull():
            new_pos = event.globalPosition().toPoint() - self.drag_pos
            self.move(new_pos)
            self.pinned_center_x = new_pos.x() + self.width() // 2
            self.pinned_y = new_pos.y()
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.pinned_center_x = self.x() + self.width() // 2
            self.pinned_y = self.y()
            self.drag_pos = QPoint()
            event.accept()

    def ensure_topmost(self):
        """Keep Notchgent at the very head of the HWND_TOPMOST layer above fullscreen apps."""
        try:
            hwnd = int(self.winId())
            win32gui.SetWindowPos(
                hwnd, win32con.HWND_TOPMOST,
                0, 0, 0, 0,
                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE | win32con.SWP_SHOWWINDOW
            )
        except Exception:
            pass

    def _on_anim_finished(self):
        if not self.is_expanded:
            self.expanded_widget.hide()
            self.ensure_topmost()

    def collapse(self):
        self.is_expanded = False
        target_w, target_h = 390, 48
        if self.pinned_center_x is None:
            screen = QApplication.primaryScreen().geometry()
            self.pinned_center_x = screen.width() // 2
        x = self.pinned_center_x - target_w // 2
        y = self.pinned_y
        target_rect = QRect(x, y, target_w, target_h)

        if not self.isVisible() or self.width() <= 10:
            self.expanded_widget.hide()
            self.setGeometry(target_rect)
            self.ensure_topmost()
            return

        self.anim.stop()
        self.anim.setDuration(220)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.anim.setStartValue(self.geometry())
        self.anim.setEndValue(target_rect)
        self.anim.start()

    def expand(self):
        self.is_expanded = True
        self.expanded_widget.show()
        target_w, target_h = 540, 224
        if self.pinned_center_x is None:
            screen = QApplication.primaryScreen().geometry()
            self.pinned_center_x = screen.width() // 2
        x = self.pinned_center_x - target_w // 2
        y = self.pinned_y
        target_rect = QRect(x, y, target_w, target_h)

        self.anim.stop()
        self.anim.setDuration(260)
        self.anim.setEasingCurve(QEasingCurve.Type.OutBack)
        self.anim.setStartValue(self.geometry())
        self.anim.setEndValue(target_rect)
        self.anim.start()

        self.ensure_topmost()
        self.raise_()
        self.activateWindow()

    def setup_watcher(self):
        self.watcher = TranscriptWatcher()
        self.watcher.action_pending.connect(self.on_action_pending)
        self.watcher.action_cleared.connect(self.on_action_cleared)

        # Poll transcript every 400 milliseconds
        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self.watcher.check_for_updates)
        self.poll_timer.start(400)

        # Movie mode timer
        self.movie_timer = QTimer(self)
        self.movie_timer.timeout.connect(self.on_movie_timer_tick)
        self.movie_timer.start(1000)

        # Active window tracker timer (tracks user's movie / working app)
        self.active_tracker_timer = QTimer(self)
        self.active_tracker_timer.timeout.connect(self.track_active_window)
        self.active_tracker_timer.start(150)

    def track_active_window(self):
        # Continually re-assert topmost layer so Notchgent stays over fullscreen media players
        self.ensure_topmost()
        try:
            fg = win32gui.GetForegroundWindow()
            if not fg or not win32gui.IsWindow(fg):
                return
            if fg == int(self.winId()):
                return
            _, pid = win32process.GetWindowThreadProcessId(fg)
            proc = psutil.Process(pid)
            pname = proc.name().lower()
            if "code" in pname:
                return
            self.last_user_hwnd = fg
        except Exception:
            pass

    def on_action_pending(self, action: dict):
        tool_name = action.get("tool_name", "Tool")
        args = action.get("args", {})
        step_idx = action.get("step_index", 0)

        self.current_workspace_hints = action.get("workspace_hints", [])
        workspace_display = self.current_workspace_hints[0] if self.current_workspace_hints else ""

        self.ensure_topmost()
        self.status_dot.setStyleSheet("color: #f59e0b;")  # Amber glow
        if workspace_display:
            self.status_label.setText(f"Approval Needed • {workspace_display}")
        else:
            self.status_label.setText(f"Approval Needed (Step {step_idx})")

        # Snapshot active user movie window before Notchgent might gain mouse attention
        try:
            fg = win32gui.GetForegroundWindow()
            if fg and win32gui.IsWindow(fg) and fg != int(self.winId()):
                _, pid = win32process.GetWindowThreadProcessId(fg)
                proc = psutil.Process(pid)
                if "code" not in proc.name().lower():
                    self.last_user_hwnd = fg
        except Exception:
            pass

        if self.last_user_hwnd and win32gui.IsWindow(self.last_user_hwnd):
            self.pending_movie_hwnd = self.last_user_hwnd
        else:
            self.pending_movie_hwnd = None

        # Set Badge
        badges = {
            "run_command": "⚡ Shell Command",
            "replace_file_content": "✏️ Edit File",
            "write_to_file": "📄 Create File",
            "ask_question": "❓ Question"
        }
        self.tool_badge.setText(badges.get(tool_name, f"🛠️ {tool_name}"))

        # Details
        if tool_name == "run_command":
            cmd = args.get("CommandLine", "").strip('"')
            details = f"> {cmd}"
        elif tool_name in ("replace_file_content", "write_to_file"):
            target = os.path.basename(args.get("TargetFile", "").strip('"'))
            instr = args.get("Instruction") or args.get("Description") or args.get("toolAction", "")
            instr = instr.strip('"')
            details = f"File: {target}\n{instr}"
        else:
            details = str(args)

        self.details_box.setPlainText(details)

        # Subtle single beep once for this step (unless configured to 'none' or 'silent')
        if self.last_chime_step != step_idx:
            self.last_chime_step = step_idx
            if self.sound_mode not in ("none", "silent", "off", "false", "0"):
                def _play_subtle_beep():
                    try:
                        import winsound
                        # 850 Hz, 45ms is a slight, subtle single electronic pip
                        winsound.Beep(850, 45)
                    except Exception:
                        pass
                threading.Thread(target=_play_subtle_beep, daemon=True).start()

        # If in Movie Auto mode, auto-approve after a 1.2s delay
        if self.auto_movie_active:
            QTimer.singleShot(1200, self.on_approve_clicked)
        else:
            self.expand()

    def on_action_cleared(self):
        self.status_dot.setStyleSheet("color: #10b981;")  # Green
        if self.auto_movie_active:
            self.status_label.setText("🎬 Auto Active")
        else:
            self.status_label.setText("Notchgent • Idle")
        self.collapse()

    def on_approve_clicked(self):
        """Send '1' + Enter to VS Code and show feedback."""
        self.status_label.setText("Sending 1...")
        self.status_dot.setStyleSheet("color: #3b82f6;")
        QApplication.processEvents()

        # Watchdog: if still showing 'Sending' after 3s, safely reset status
        QTimer.singleShot(3000, self._watchdog_check)

        target_movie = self.pending_movie_hwnd or self.last_user_hwnd
        notch_hwnd = int(self.winId())
        ws_hints = list(self.current_workspace_hints)
        threading.Thread(target=self._send_key_bg, args=("1", target_movie, notch_hwnd, ws_hints), daemon=True).start()

    def on_deny_clicked(self):
        """Send '2' + Enter to VS Code and show feedback."""
        self.status_label.setText("Sending 2...")
        self.status_dot.setStyleSheet("color: #ef4444;")
        QApplication.processEvents()

        # Watchdog: if still showing 'Sending' after 3s, safely reset status
        QTimer.singleShot(3000, self._watchdog_check)

        target_movie = self.pending_movie_hwnd or self.last_user_hwnd
        notch_hwnd = int(self.winId())
        ws_hints = list(self.current_workspace_hints)
        threading.Thread(target=self._send_key_bg, args=("2", target_movie, notch_hwnd, ws_hints), daemon=True).start()

    def _send_key_bg(
        self,
        key_str: str,
        movie_hwnd: Optional[int] = None,
        notch_hwnd: Optional[int] = None,
        ws_hints: Optional[List[str]] = None
    ):
        try:
            success = send_key_to_vscode(key_str, movie_hwnd, notch_hwnd, ws_hints)
        except Exception:
            success = False
        # Emit signal to main GUI thread (thread-safe queued connection)
        self.key_sent_signal.emit(success, key_str)

    def _on_key_sent(self, success: bool, key_str: str):
        self.ensure_topmost()
        if success:
            self.status_label.setText(f"Sent {key_str} ✓")
            self.status_dot.setStyleSheet("color: #10b981;")
        else:
            self.status_label.setText("VS Code not found")
            self.status_dot.setStyleSheet("color: #f59e0b;")
        QTimer.singleShot(1800, self._restore_idle_label)

    def _watchdog_check(self):
        if self.status_label.text().startswith("Sending"):
            if self.auto_movie_active:
                mins, secs = divmod(self.auto_countdown, 60)
                self.status_label.setText(f"🎬 Auto ({mins:02d}:{secs:02d})")
                self.status_dot.setStyleSheet("color: #f97316;")
            else:
                self.status_label.setText("Notchgent • Idle")
                self.status_dot.setStyleSheet("color: #10b981;")

    def _restore_idle_label(self):
        if not self.is_expanded:
            if self.auto_movie_active:
                mins, secs = divmod(self.auto_countdown, 60)
                self.status_label.setText(f"🎬 Auto ({mins:02d}:{secs:02d})")
                self.status_dot.setStyleSheet("color: #f97316;")
            else:
                self.status_label.setText("Notchgent • Idle")
                self.status_dot.setStyleSheet("color: #10b981;")

    def toggle_movie_mode(self):
        if self.movie_mode_btn.isChecked():
            self.auto_movie_active = True
            self.auto_countdown = 900  # 15 mins
            self.status_label.setText("🎬 Auto (15m)")
            self.status_dot.setStyleSheet("color: #f97316;")
            # Start pulsating border animation
            self.pulse_phase = 0.0
            self.pulse_timer.start()
            # If an action is pending right now, approve it immediately
            if self.is_expanded:
                self.on_approve_clicked()
        else:
            self.auto_movie_active = False
            self.auto_countdown = 0
            # Stop pulsation and restore steady orange stroke
            self.pulse_timer.stop()
            self._reset_border_to_steady()
            self.movie_mode_btn.setText("🎬 Auto")
            self.status_label.setText("Notchgent • Idle")
            self.status_dot.setStyleSheet("color: #10b981;")

    def _on_pulse_tick(self):
        if not self.auto_movie_active:
            self.pulse_timer.stop()
            self._reset_border_to_steady()
            return

        self.pulse_phase += 0.08
        val = (math.sin(self.pulse_phase) + 1.0) / 2.0

        # Border alpha breathes from 0.35 to 1.0
        alpha = 0.35 + val * 0.65
        border_w = 1.3 + val * 0.8
        # Color shifts between warm orange (245, 110, 20) and glowing electric orange (255, 155, 45)
        r = int(245 + val * 10)
        g = int(110 + val * 45)
        b = int(20 + val * 25)

        self.frame.setStyleSheet(f"""
            #MainFrame {{
                background-color: rgba(18, 20, 26, 0.90);
                border: {border_w:.1f}px solid rgba({r}, {g}, {b}, {alpha:.2f});
                border-top: none;
                border-top-left-radius: 0px;
                border-top-right-radius: 0px;
                border-bottom-left-radius: 20px;
                border-bottom-right-radius: 20px;
            }}
        """)

    def _reset_border_to_steady(self):
        self.frame.setStyleSheet("""
            #MainFrame {
                background-color: rgba(18, 20, 26, 0.90);
                border: 1.5px solid rgba(249, 115, 22, 0.90);
                border-top: none;
                border-top-left-radius: 0px;
                border-top-right-radius: 0px;
                border-bottom-left-radius: 20px;
                border-bottom-right-radius: 20px;
            }
        """)

    def on_movie_timer_tick(self):
        if self.auto_movie_active:
            self.auto_countdown -= 1
            if self.auto_countdown <= 0:
                self.movie_mode_btn.setChecked(False)
                self.toggle_movie_mode()
                return

            mins, secs = divmod(self.auto_countdown, 60)
            self.movie_mode_btn.setText(f"🎬 {mins:02d}:{secs:02d}")

    def setup_hotkeys(self):
        if not PYNPUT_AVAILABLE:
            return

        def on_1():
            QTimer.singleShot(0, self.on_approve_clicked)

        def on_2():
            QTimer.singleShot(0, self.on_deny_clicked)

        try:
            hotkeys = {
                "<alt>+1": on_1,
                "<alt>+a": on_1,
                "<f8>": on_1,
                "<alt>+2": on_2,
                "<alt>+d": on_2,
                "<f9>": on_2
            }
            self.listener = keyboard.GlobalHotKeys(hotkeys)
            self.listener.daemon = True
            self.listener.start()
        except Exception:
            pass


def main():
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("notchgent.hud.app.1")
    except Exception:
        pass
    ensure_default_desktop()
    kill_previous_instance()
    app = QApplication(sys.argv)
    icon_path = os.path.join(SCRIPT_DIR, "app_icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    hud = NotchgentHUD()
    hud.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
