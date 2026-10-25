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
import re
import sqlite3
from typing import Optional, Tuple, Dict, Any, List

# Ensure High DPI awareness
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

from PyQt6.QtCore import (
    Qt, QPoint, QRect, QSize, pyqtSignal, QObject, QTimer,
    QPropertyAnimation, QEasingCurve
)
from PyQt6.QtGui import (
    QColor, QFont, QIcon
)
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QGraphicsDropShadowEffect, QFrame, QTextEdit
)

from icons import get_svg_icon, get_svg_pixmap


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


from remote_server import RemoteServer
from tunnel_manager import TunnelManager
from remote_dialog import RemoteDialog


def set_keep_awake(enable: bool = True):
    """Keep system awake (prevent PC sleep) while Notchgent is running."""
    try:
        ES_CONTINUOUS = 0x80000000
        ES_SYSTEM_REQUIRED = 0x00000001
        ES_AWAYMODE_REQUIRED = 0x00000040
        if enable:
            ctypes.windll.kernel32.SetThreadExecutionState(
                ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_AWAYMODE_REQUIRED
            )
        else:
            ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
    except Exception:
        pass


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
            my_pid = os.getpid()
            parent_pid = None
            try:
                parent_pid = psutil.Process(my_pid).ppid()
            except Exception:
                pass
            if old_pid != my_pid and old_pid != parent_pid:
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


def release_all_modifiers():
    """Forcibly release Alt, Ctrl, Shift, and Win keys if currently pressed or simulated."""
    vks = (
        win32con.VK_MENU, win32con.VK_LMENU, win32con.VK_RMENU,
        win32con.VK_CONTROL, win32con.VK_LCONTROL, win32con.VK_RCONTROL,
        win32con.VK_SHIFT, win32con.VK_LSHIFT, win32con.VK_RSHIFT,
        win32con.VK_LWIN, win32con.VK_RWIN
    )
    for vk in vks:
        try:
            async_down = bool(win32api.GetAsyncKeyState(vk) & 0x8000)
            key_down = bool(win32api.GetKeyState(vk) & 0x8000)
            if async_down or key_down:
                win32api.keybd_event(vk, 0, win32con.KEYEVENTF_KEYUP, 0)
        except Exception:
            pass


# Tools that actually require user confirmation/interaction in Antigravity CLI/IDE
APPROVAL_REQUIRED_TOOLS = {
    "run_command", "ask_question"
}

# Tools that are strictly read-only and never require user approval
READ_ONLY_TOOLS = {
    "read_file", "read_file_range", "search_web", "fetch_web_page", "list_dir",
    "view_outline", "view_symbol", "get_definition", "find_by_name", "grep",
    "inspect_code_element", "codebase_investigation", "read_image_file",
    "manage_task", "send_message", "schedule", "invoke_subagent",
    "define_subagent", "manage_subagents", "read_transcript"
}


def find_vscode_window(workspace_hints: Optional[List[str]] = None) -> Tuple[Optional[int], str]:
    """Find the matching VS Code window handle for the given workspace, or None if no match."""
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
                pid = pid & 0xFFFFFFFF
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

    # 1. Match candidates strictly against workspace hints (e.g. TTS, notchgent, MYPALV2)
    if workspace_hints:
        hints = [workspace_hints] if isinstance(workspace_hints, str) else list(workspace_hints)
        for h in hints:
            h_clean = h.lower().strip()
            if not h_clean or len(h_clean) < 2:
                continue
            for hwnd, title, z in candidates:
                t_lower = title.lower()
                # Check for workspace word in VS Code title
                if (
                    f"- {h_clean} -" in t_lower
                    or t_lower.startswith(f"{h_clean} -")
                    or f"[{h_clean}]" in t_lower
                    or f" {h_clean} " in t_lower
                    or t_lower.endswith(f"- {h_clean}")
                    or re.search(r'\b' + re.escape(h_clean) + r'\b', t_lower)
                ):
                    return hwnd, title

        # Strict Multi-Workspace Isolation: If workspace hints were provided but none of the open
        # VS Code windows matched, DO NOT guess or inject keystrokes into an unrelated VS Code window!
        return None, ""

    # 2. If NO workspace hints were provided at all, and exactly 1 VS Code window exists:
    if len(candidates) == 1:
        return candidates[0][0], candidates[0][1]

    # If multiple VS Code windows exist and we have no hint which one to target, DO NOT guess!
    return None, ""

def force_foreground_window(hwnd: int) -> bool:
    """Robustly brings hwnd to foreground without stealing focus to menu bar or sticking Alt."""
    if not hwnd or not win32gui.IsWindow(hwnd):
        return False
    if win32gui.GetForegroundWindow() == hwnd:
        return True

    ensure_default_desktop()

    try:
        ctypes.windll.user32.AllowSetForegroundWindow(-1)
        ctypes.windll.user32.LockSetForegroundWindow(2)  # LSFW_UNLOCK

        # Simulate Alt key release to grant Windows foreground change permission
        win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)
        win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)

        fg = win32gui.GetForegroundWindow()
        if fg and win32gui.IsWindow(fg) and fg != hwnd:
            fg_thread = win32process.GetWindowThreadProcessId(fg)[0]
            target_thread = win32process.GetWindowThreadProcessId(hwnd)[0]
            my_thread = win32api.GetCurrentThreadId()

            attached_fg = False
            attached_target = False
            try:
                win32process.AttachThreadInput(my_thread, fg_thread, True)
                attached_fg = True
                win32process.AttachThreadInput(my_thread, target_thread, True)
                attached_target = True

                win32gui.BringWindowToTop(hwnd)
                win32gui.SetForegroundWindow(hwnd)
            finally:
                if attached_target:
                    try:
                        win32process.AttachThreadInput(my_thread, target_thread, False)
                    except Exception:
                        pass
                if attached_fg:
                    try:
                        win32process.AttachThreadInput(my_thread, fg_thread, False)
                    except Exception:
                        pass

        if win32gui.GetForegroundWindow() != hwnd:
            # Fallback 1: Native Windows SwitchToThisWindow API
            try:
                ctypes.windll.user32.SwitchToThisWindow(hwnd, True)
            except Exception:
                pass

        if win32gui.GetForegroundWindow() != hwnd:
            # Fallback 2: Show and bring to top
            try:
                win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
                win32gui.SetForegroundWindow(hwnd)
                win32gui.BringWindowToTop(hwnd)
            except Exception:
                pass
    finally:
        # Guarantee no modifier keys are left held down
        release_all_modifiers()

    return win32gui.GetForegroundWindow() == hwnd


def send_key_to_vscode(
    key_text: str = "1",
    movie_hwnd: Optional[int] = None,
    notch_hwnd: Optional[int] = None,
    workspace_hints: Optional[List[str]] = None
) -> bool:
    """Send '1' or '2' + Enter strictly to VS Code. Never injects into other apps."""
    ensure_default_desktop()
    target_hwnd, title = find_vscode_window(workspace_hints)
    if not target_hwnd or not win32gui.IsWindow(target_hwnd):
        return False

    was_minimized = bool(win32gui.IsIconic(target_hwnd))

    try:
        # Pre-flight: Ensure any physical or stuck modifier keys are fully cleared
        for _ in range(12):
            if not (win32api.GetAsyncKeyState(win32con.VK_MENU) & 0x8000):
                break
            time.sleep(0.01)
        release_all_modifiers()

        # 1. If VS Code is minimized, restore it
        if was_minimized:
            win32gui.ShowWindow(target_hwnd, win32con.SW_RESTORE)
            for _ in range(10):
                if not win32gui.IsIconic(target_hwnd):
                    break
                time.sleep(0.015)

        # 2. Focus VS Code
        for _ in range(12):
            if force_foreground_window(target_hwnd):
                break
            time.sleep(0.02)

        # 3. CRITICAL SAFEGUARD: Verify that VS Code is genuinely the active foreground window!
        # If another app (Word, File Explorer, Chrome, etc.) is in the foreground, ABORT IMMEDIATELY.
        # This completely guarantees we never type '1' or Enter into the user's active documents!
        current_fg = win32gui.GetForegroundWindow()
        if current_fg != target_hwnd:
            if was_minimized:
                try:
                    win32gui.ShowWindow(target_hwnd, win32con.SW_MINIMIZE)
                except Exception:
                    pass
            return False

        time.sleep(0.02)

        # Pre-keystroke check: ensure all modifiers are up before sending key
        release_all_modifiers()
        time.sleep(0.01)

        # 4. Send keystroke + enter strictly into VS Code terminal
        vk = ord(key_text[0].upper()) if key_text else ord('1')
        win32api.keybd_event(vk, 0, 0, 0)
        win32api.keybd_event(vk, 0, win32con.KEYEVENTF_KEYUP, 0)
        time.sleep(0.02)

        release_all_modifiers()
        time.sleep(0.01)

        win32api.keybd_event(win32con.VK_RETURN, 0, 0, 0)
        win32api.keybd_event(win32con.VK_RETURN, 0, win32con.KEYEVENTF_KEYUP, 0)
        time.sleep(0.04)

        return True

    except Exception:
        return False
    finally:
        release_all_modifiers()

        # 1. If VS Code was minimized before, tuck it back into the taskbar immediately
        if was_minimized:
            try:
                win32gui.ShowWindow(target_hwnd, win32con.SW_MINIMIZE)
            except Exception:
                pass

        # 2. Restore foreground focus to the user's previous working window (Word, Explorer, or Video)
        if movie_hwnd and win32gui.IsWindow(movie_hwnd) and movie_hwnd != target_hwnd:
            try:
                force_foreground_window(movie_hwnd)
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


def get_recent_transcripts(max_age_seconds: int = 1800) -> List[str]:
    """Find all transcript.jsonl files modified within max_age_seconds (default 30 mins)."""
    pattern = os.path.join(BRAIN_DIR, "*", ".system_generated", "logs", "transcript.jsonl")
    files = glob.glob(pattern)
    now = time.time()
    recent = []
    for f in files:
        try:
            mtime = os.path.getmtime(f)
            if (now - mtime) <= max_age_seconds:
                recent.append((f, mtime))
        except Exception:
            pass
    recent.sort(key=lambda x: x[1], reverse=True)
    return [f[0] for f in recent]


def extract_workspace_hints(args: dict, transcript_file: Optional[str] = None) -> List[str]:
    """Extract candidate workspace/folder names strictly for this specific transcript."""
    hints = []
    # 1. From path arguments in the current tool call
    for key in ("Cwd", "TargetFile", "AbsolutePath", "path", "directory", "Path", "file_path"):
        raw_path = args.get(key)
        if raw_path and isinstance(raw_path, str):
            clean = raw_path.strip('"\'')
            norm = os.path.normpath(clean)
            parts = [p for p in norm.split(os.sep) if p and not p.endswith(":") and p != "."]
            for part in reversed(parts):
                if len(part) > 1 and part.lower() not in (
                    "src", "app", "components", "lib", "node_modules", "pages", "dist", "build", "public", ".gemini"
                ):
                    if part not in hints:
                        hints.append(part)
                    break
    if hints:
        return hints

    # 2. From CommandLine argument (e.g. `cd C:\path\to\proj`, `-Path "C:\path\to\proj"`)
    cmd = args.get("CommandLine", "")
    if cmd and isinstance(cmd, str):
        path_matches = re.findall(r'[A-Za-z]:\\[^\s"\'<>|]+', cmd)
        for pm in path_matches:
            norm = os.path.normpath(pm)
            parts = [p for p in norm.split(os.sep) if p and not p.endswith(":") and p != "."]
            for part in reversed(parts):
                if len(part) > 1 and part.lower() not in (
                    "src", "app", "components", "lib", "node_modules", "pages", "dist", "build", "public", ".gemini"
                ):
                    if part not in hints:
                        hints.append(part)
                    break
    if hints:
        return hints

    # 3. Directly from Antigravity conversation database (conversations/<conv_id>.db)
    conv_id = None
    if transcript_file and os.path.exists(transcript_file):
        try:
            norm = os.path.normpath(transcript_file)
            parts = norm.split(os.sep)
            if "brain" in parts:
                b_idx = parts.index("brain")
                if b_idx + 1 < len(parts):
                    conv_id = parts[b_idx + 1]
                    db_path = os.path.expanduser(f"~/.gemini/antigravity-cli/conversations/{conv_id}.db")
                    if os.path.exists(db_path):
                        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
                        cur = conn.cursor()
                        cur.execute("SELECT data FROM trajectory_metadata_blob LIMIT 1;")
                        row = cur.fetchone()
                        conn.close()
                        if row and row[0]:
                            matches = re.findall(r'file:///([A-Za-z]:/[^\x00-\x1f\"\'<>]+)', row[0].decode('utf-8', errors='ignore'))
                            for m in matches:
                                clean_m = m.rstrip('z\x00')
                                ws_name = os.path.basename(os.path.normpath(clean_m))
                                if ws_name and len(ws_name) > 1 and ws_name not in hints:
                                    hints.append(ws_name)
        except Exception:
            pass
    if hints:
        return hints

    # 4. Check specific agy.exe process associated with this conv_id
    if conv_id:
        try:
            for p in psutil.process_iter(['pid', 'name']):
                if p.info['name'] and 'agy' in p.info['name'].lower():
                    proc = psutil.Process(p.info['pid'])
                    try:
                        open_files = [f.path for f in proc.open_files()]
                        if any(conv_id in f for f in open_files):
                            cwd = proc.cwd()
                            if cwd:
                                ws_name = os.path.basename(os.path.normpath(cwd))
                                if ws_name and len(ws_name) > 1 and ws_name not in hints:
                                    hints.append(ws_name)
                                    return hints
                    except Exception:
                        pass
        except Exception:
            pass

    # 5. Search backwards in this SPECIFIC transcript_file for recent Cwd, TargetFile, or Path
    if not hints and transcript_file and os.path.exists(transcript_file):
        try:
            with open(transcript_file, "r", encoding="utf-8", errors="ignore") as f:
                f.seek(0, os.SEEK_END)
                size = f.tell()
                read_size = min(size, 32768)
                f.seek(size - read_size)
                lines = [l.strip() for l in f.readlines() if l.strip()]
            for line in reversed(lines):
                if '"Cwd"' in line or '"TargetFile"' in line or '"AbsolutePath"' in line or '"Path"' in line:
                    try:
                        obj = json.loads(line)
                        for tc in obj.get("tool_calls", []):
                            a = tc.get("args", {})
                            if isinstance(a, str):
                                try:
                                    a = json.loads(a)
                                except Exception:
                                    pass
                            for k in ("Cwd", "TargetFile", "AbsolutePath", "path", "Path"):
                                p = a.get(k)
                                if p and isinstance(p, str):
                                    norm = os.path.normpath(p.strip('"\''))
                                    parts = [x for x in norm.split(os.sep) if x and not x.endswith(":") and x != "."]
                                    for part in reversed(parts):
                                        if len(part) > 1 and part.lower() not in ("src", "app", "components", "lib", "node_modules", ".gemini"):
                                            if part not in hints:
                                                hints.append(part)
                    except Exception:
                        pass
                if hints:
                    break
        except Exception:
            pass

    return hints

def check_transcript_pending_action(transcript_path: str) -> Optional[dict]:
    """Check if a specific transcript file currently has a pending tool call awaiting approval."""
    if not transcript_path or not os.path.exists(transcript_path):
        return None

    try:
        with open(transcript_path, "r", encoding="utf-8", errors="ignore") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            if size == 0:
                return None
            read_size = min(size, 8192)
            f.seek(size - read_size)
            lines = [l.strip() for l in f.readlines() if l.strip()]

        if not lines:
            return None

        last_obj = json.loads(lines[-1])
        step_idx = last_obj.get("step_index", 0)
        step_type = last_obj.get("type", "")

        # If the last entry is PLANNER_RESPONSE with tool_calls, check if any tool requires user approval
        if step_type == "PLANNER_RESPONSE" and last_obj.get("tool_calls"):
            tool_call = last_obj["tool_calls"][0]
            raw_tool_name = tool_call.get("name", "Tool")
            tool_name = raw_tool_name.split(":")[-1]

            # STRICT FILTER: Read-only and non-approval tools NEVER trigger Notchgent approval!
            if tool_name not in APPROVAL_REQUIRED_TOOLS:
                return None

            args = tool_call.get("args", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = {"raw": args}

            workspace_hints = extract_workspace_hints(args, transcript_path)

            return {
                "transcript_file": transcript_path,
                "step_index": step_idx,
                "tool_name": tool_name,
                "args": args,
                "workspace_hints": workspace_hints
            }
    except Exception:
        pass

    return None

class TranscriptWatcher(QObject):
    action_pending = pyqtSignal(dict)  # Emitted when an action is awaiting approval
    action_cleared = pyqtSignal()      # Emitted when agent is idle or finished

    def __init__(self):
        super().__init__()
        self.currently_pending = False
        self.last_pending_key = None

    def check_for_updates(self):
        recent_transcripts = get_recent_transcripts(max_age_seconds=1800)
        if not recent_transcripts:
            if self.currently_pending:
                self.currently_pending = False
                self.last_pending_key = None
                self.action_cleared.emit()
            return

        active_pending = []
        for t_file in recent_transcripts[:8]:
            act = check_transcript_pending_action(t_file)
            if act:
                active_pending.append(act)

        if active_pending:
            action = active_pending[0]
            key = (action["transcript_file"], action["step_index"])
            if not self.currently_pending or key != self.last_pending_key:
                self.currently_pending = True
                self.last_pending_key = key
                self.action_pending.emit(action)
        else:
            if self.currently_pending:
                self.currently_pending = False
                self.last_pending_key = None
                self.action_cleared.emit()


class NotchgentHUD(QWidget):
    key_sent_signal = pyqtSignal(bool, str)
    remote_action_signal = pyqtSignal(str)
    remote_toggle_auto_signal = pyqtSignal()
    remote_toggle_mute_signal = pyqtSignal()
    tunnel_url_signal = pyqtSignal(str)
    tunnel_status_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.key_sent_signal.connect(self._on_key_sent)
        self.remote_action_signal.connect(self._handle_remote_action)
        self.remote_toggle_auto_signal.connect(self._handle_remote_toggle_auto)
        self.remote_toggle_mute_signal.connect(self._handle_remote_toggle_mute)
        self.tunnel_url_signal.connect(self._on_tunnel_url_discovered)
        self.tunnel_status_signal.connect(self._on_tunnel_status_changed)

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

        self.remote_dialog: Optional[RemoteDialog] = None

        # Pulsation for Auto Movie Mode
        self.pulse_phase = 0.0
        self.pulse_timer = QTimer(self)
        self.pulse_timer.setInterval(40)
        self.pulse_timer.timeout.connect(self._on_pulse_tick)
        self.frame_shadow: Optional[QGraphicsDropShadowEffect] = None

        self.sound_mode = "beep"
        remote_port = 5151
        config_path = os.path.join(SCRIPT_DIR, "config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    self.sound_mode = str(cfg.get("sound", "beep")).lower()
                    remote_port = int(cfg.get("port", 5151))
            except Exception:
                pass

        self.is_muted = self.sound_mode in ("none", "silent", "off", "false", "0")

        self.is_sending_keys = False
        self.dispatched_keys = set()
        self.current_action_file = ''
        self.current_action_step = -1
        self._auto_timer: Optional[QTimer] = None
        release_all_modifiers()

        # Start Remote Server on local port
        self.remote_server = RemoteServer(
            port=remote_port,
            on_action_callback=lambda k: self.remote_action_signal.emit(k) or True,
            on_toggle_auto_callback=lambda: self.remote_toggle_auto_signal.emit() or self.auto_movie_active,
            on_toggle_mute_callback=lambda: self.remote_toggle_mute_signal.emit() or self.is_muted,
            is_muted=self.is_muted
        )
        self.remote_server.start()

        # Start Tunnel Manager for zero-config remote access
        self.tunnel_manager = TunnelManager(
            local_port=remote_port,
            on_url_ready=lambda u: self.tunnel_url_signal.emit(u),
            on_status_change=lambda s: self.tunnel_status_signal.emit(s)
        )
        self.tunnel_manager.start()

        # Timer to update remote device count in HUD button
        self.remote_device_timer = QTimer(self)
        self.remote_device_timer.timeout.connect(self._sync_remote_devices)
        self.remote_device_timer.start(2000)

        # Keep Windows awake while Notchgent is running
        set_keep_awake(True)

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
        self.setMinimumSize(340, 40)
        self.setMaximumSize(720, 340)

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
        self.status_label.setMinimumWidth(130)

        self.remote_mode_btn = QPushButton("Remote")
        self.remote_mode_btn.setObjectName("RemoteModeBtn")
        self.remote_mode_btn.setIcon(get_svg_icon("phone", "#ffffff", 13))
        self.remote_mode_btn.setIconSize(QSize(13, 13))
        self.remote_mode_btn.setFixedSize(86, 24)
        self.remote_mode_btn.clicked.connect(self.toggle_remote_dialog)

        self.movie_mode_btn = QPushButton("Auto")
        self.movie_mode_btn.setObjectName("MovieModeBtn")
        self.movie_mode_btn.setIcon(get_svg_icon("clapperboard", "#ffffff", 13))
        self.movie_mode_btn.setIconSize(QSize(13, 13))
        self.movie_mode_btn.setCheckable(True)
        self.movie_mode_btn.setFixedSize(80, 24)
        self.movie_mode_btn.clicked.connect(self.toggle_movie_mode)

        self.mute_btn = QPushButton()
        self.mute_btn.setObjectName("MuteBtn")
        self.mute_btn.setFixedSize(28, 24)
        self.mute_btn.clicked.connect(self.toggle_mute)
        self._update_mute_ui()

        self.close_btn = QPushButton()
        self.close_btn.setObjectName("CloseBtn")
        self.close_btn.setIcon(get_svg_icon("x", "#9ca3af", 11))
        self.close_btn.setIconSize(QSize(11, 11))
        self.close_btn.setFixedSize(20, 20)
        self.close_btn.clicked.connect(self.close)

        self.header_layout.addWidget(self.status_dot)
        self.header_layout.addWidget(self.status_label, 1)
        self.header_layout.addWidget(self.remote_mode_btn)
        self.header_layout.addWidget(self.movie_mode_btn)
        self.header_layout.addWidget(self.mute_btn)
        self.header_layout.addWidget(self.close_btn)

        self.frame_layout.addWidget(self.header_widget)

        # --- Expanded Content Section (Visible when action pending) ---
        self.expanded_widget = QWidget()
        self.expanded_layout = QVBoxLayout(self.expanded_widget)
        self.expanded_layout.setContentsMargins(0, 6, 0, 0)
        self.expanded_layout.setSpacing(8)

        # Badge Container
        badge_row = QHBoxLayout()
        badge_row.setContentsMargins(0, 0, 0, 0)

        self.tool_badge_frame = QFrame()
        self.tool_badge_frame.setObjectName("ToolBadge")
        badge_layout = QHBoxLayout(self.tool_badge_frame)
        badge_layout.setContentsMargins(6, 2, 8, 2)
        badge_layout.setSpacing(6)

        self.tool_badge_icon = QLabel()
        self.tool_badge_icon.setFixedSize(14, 14)
        self.tool_badge_icon.setPixmap(get_svg_pixmap("zap", "#c4b5fd", 14))

        self.tool_badge_text = QLabel("Tool Execution")
        self.tool_badge_text.setObjectName("ToolBadgeText")

        badge_layout.addWidget(self.tool_badge_icon)
        badge_layout.addWidget(self.tool_badge_text)

        badge_row.addWidget(self.tool_badge_frame)
        badge_row.addStretch()
        self.expanded_layout.addLayout(badge_row)

        # Details Box
        self.details_box = QTextEdit()
        self.details_box.setObjectName("DetailsBox")
        self.details_box.setReadOnly(True)
        self.details_box.setFixedHeight(75)
        self.expanded_layout.addWidget(self.details_box)

        # Buttons Row: [ Approve (Alt+1) ] [ Reject (Alt+2) ]
        self.btn_layout = QHBoxLayout()
        self.btn_layout.setSpacing(8)

        self.approve_btn = QPushButton(" 1. Approve (Alt+1)")
        self.approve_btn.setObjectName("ApproveBtn")
        self.approve_btn.setIcon(get_svg_icon("check", "#ffffff", 14))
        self.approve_btn.setIconSize(QSize(14, 14))
        self.approve_btn.setFixedHeight(34)
        self.approve_btn.clicked.connect(self.on_approve_clicked)

        self.deny_btn = QPushButton(" 2 (Alt+2)")
        self.deny_btn.setObjectName("DenyBtn")
        self.deny_btn.setIcon(get_svg_icon("x", "#fca5a5", 13))
        self.deny_btn.setIconSize(QSize(13, 13))
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
            #RemoteModeBtn {
                background-color: rgba(255, 255, 255, 0.1);
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 0.18);
                border-radius: 12px;
                font-size: 11px;
                font-weight: 600;
                padding: 0 4px;
            }
            #RemoteModeBtn:hover {
                background-color: rgba(249, 115, 22, 0.25);
                border-color: rgba(249, 115, 22, 0.5);
                color: #ffffff;
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
            #MuteBtn {
                background-color: rgba(255, 255, 255, 0.1);
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 0.18);
                border-radius: 12px;
                padding: 0;
            }
            #MuteBtn:hover {
                background-color: rgba(255, 255, 255, 0.2);
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
                background-color: rgba(139, 92, 246, 0.22);
                border: 1px solid rgba(139, 92, 246, 0.45);
                border-radius: 8px;
            }
            #ToolBadgeText {
                color: #c4b5fd;
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
            if self.remote_dialog and self.remote_dialog.isVisible():
                rx = new_pos.x() + (self.width() - self.remote_dialog.width()) // 2
                ry = new_pos.y() + self.height() + 8
                self.remote_dialog.move(rx, ry)
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
        target_w, target_h = 495, 48
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
        target_w, target_h = 580, 224
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
        t_file = action.get("transcript_file", "")

        self.current_action_file = t_file
        self.current_action_step = step_idx

        # If this exact step was already approved or rejected, do not re-prompt or send keys again
        if (t_file, step_idx) in self.dispatched_keys:
            return

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
        tool_icons = {
            "run_command": ("terminal", "Shell Command"),
            "replace_file_content": ("file_edit", "Edit File"),
            "write_to_file": ("file_plus", "Create File"),
            "edit_file": ("file_edit", "Edit File"),
            "write_file": ("file_plus", "Create File"),
            "ask_question": ("help_circle", "Question")
        }
        icon_name, badge_label = tool_icons.get(tool_name, ("zap", tool_name))
        self.tool_badge_icon.setPixmap(get_svg_pixmap(icon_name, "#c4b5fd", 14))
        self.tool_badge_text.setText(badge_label)


        # Details
        if tool_name == "run_command":
            cmd = args.get("CommandLine", "").strip('"')
            details = f"> {cmd}"
        elif tool_name in ("replace_file_content", "write_to_file", "edit_file", "write_file"):
            target = os.path.basename(args.get("TargetFile", "") or args.get("Path", "")).strip('"')
            instr = (
                args.get("Instruction")
                or args.get("Description")
                or args.get("toolSummary")
                or args.get("toolAction", "")
            )
            instr = instr.strip('"') if isinstance(instr, str) else ""
            details = f"File: {target}\n{instr}" if instr else f"File: {target}"
        else:
            details = str(args)

        self.details_box.setPlainText(details)

        # Broadcast state to remote mobile clients
        self.remote_server.update_state("pending", action, workspace_display, self.auto_movie_active, is_muted=self.is_muted)

        # Subtle single beep once for this step (unless muted or configured to 'none'/'silent')
        if self.last_chime_step != step_idx:
            self.last_chime_step = step_idx
            if not self.is_muted and self.sound_mode not in ("none", "silent", "off", "false", "0"):
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
            if self._auto_timer and self._auto_timer.isActive():
                self._auto_timer.stop()
            self._auto_timer = QTimer(self)
            self._auto_timer.setSingleShot(True)
            self._auto_timer.timeout.connect(self.on_approve_clicked)
            self._auto_timer.start(1200)
        else:
            self.expand()

    def on_action_cleared(self):
        self.current_action_file = ""
        self.current_action_step = -1
        self.status_dot.setStyleSheet("color: #10b981;")  # Green
        if self.auto_movie_active:
            self.status_label.setText("Auto Active")
        else:
            self.status_label.setText("Notchgent • Idle")
        self.remote_server.update_state("idle", None, "", self.auto_movie_active, is_muted=self.is_muted)
        self.collapse()

    def on_approve_clicked(self):
        """Send '1' + Enter to VS Code and show feedback."""
        if getattr(self, "is_sending_keys", False):
            return
        current_key = (getattr(self, "current_action_file", ""), getattr(self, "current_action_step", -1))
        if current_key[0] and current_key[1] >= 0:
            if current_key in self.dispatched_keys:
                return
        self.is_sending_keys = True
        self.status_label.setText("Sending 1...")
        self.status_dot.setStyleSheet("color: #3b82f6;")
        QApplication.processEvents()

        # Watchdog: if still showing 'Sending' after 3.5s, safely reset status
        QTimer.singleShot(3500, self._watchdog_check)

        target_movie = self.pending_movie_hwnd or self.last_user_hwnd
        notch_hwnd = int(self.winId())
        ws_hints = list(self.current_workspace_hints)
        threading.Thread(target=self._send_key_bg, args=("1", target_movie, notch_hwnd, ws_hints), daemon=True).start()

    def on_deny_clicked(self):
        """Send '2' + Enter to VS Code and show feedback."""
        if getattr(self, "is_sending_keys", False):
            return
        current_key = (getattr(self, "current_action_file", ""), getattr(self, "current_action_step", -1))
        if current_key[0] and current_key[1] >= 0:
            if current_key in self.dispatched_keys:
                return
        self.is_sending_keys = True
        self.status_label.setText("Sending 2...")
        self.status_dot.setStyleSheet("color: #ef4444;")
        QApplication.processEvents()

        # Watchdog: if still showing 'Sending' after 3.5s, safely reset status
        QTimer.singleShot(3500, self._watchdog_check)

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
        self.is_sending_keys = False
        release_all_modifiers()
        self.ensure_topmost()
        ws = self.current_workspace_hints[0] if self.current_workspace_hints else ""
        if success:
            current_key = (getattr(self, "current_action_file", ""), getattr(self, "current_action_step", -1))
            if current_key[0] and current_key[1] >= 0:
                self.dispatched_keys.add(current_key)
                if len(self.dispatched_keys) > 60:
                    self.dispatched_keys = set(list(self.dispatched_keys)[-30:])
            self.current_action_file = ''
            self.current_action_step = -1
            if ws:
                self.status_label.setText(f"Sent {key_str} ({ws})")
            else:
                self.status_label.setText(f"Sent {key_str}")
            self.status_dot.setStyleSheet("color: #10b981;")
            self.remote_server.update_state("idle", None, "", self.auto_movie_active)
            QTimer.singleShot(1800, self._restore_idle_label)
        else:
            # Focusing VS Code was not possible or focus was blocked
            self.status_dot.setStyleSheet("color: #f59e0b;")
            if ws:
                self.status_label.setText(f"Focusing '{ws}'...")
            else:
                self.status_label.setText("Focusing VS Code...")
            # If in Auto mode, automatically retry after a 1s delay so it unstucks by itself!
            if self.auto_movie_active and getattr(self, "current_action_file", ""):
                QTimer.singleShot(1000, self.on_approve_clicked)

    def _watchdog_check(self):
        self.is_sending_keys = False
        self.dispatched_keys = set()
        self.current_action_file = ''
        self.current_action_step = -1
        release_all_modifiers()
        if self.status_label.text().startswith("Sending"):
            if self.auto_movie_active:
                mins, secs = divmod(self.auto_countdown, 60)
                self.status_label.setText(f"Auto ({mins:02d}:{secs:02d})")
                self.status_dot.setStyleSheet("color: #f97316;")
            else:
                self.status_label.setText("Notchgent • Idle")
                self.status_dot.setStyleSheet("color: #10b981;")

    def _restore_idle_label(self):
        if not self.is_expanded:
            if self.auto_movie_active:
                mins, secs = divmod(self.auto_countdown, 60)
                self.status_label.setText(f"Auto ({mins:02d}:{secs:02d})")
                self.status_dot.setStyleSheet("color: #f97316;")
            else:
                self.status_label.setText("Notchgent • Idle")
                self.status_dot.setStyleSheet("color: #10b981;")

    def toggle_movie_mode(self):
        if self.movie_mode_btn.isChecked():
            self.auto_movie_active = True
            self.auto_countdown = 900  # 15 mins
            self.status_label.setText("Auto (15m)")
            self.status_dot.setStyleSheet("color: #f97316;")
            self.movie_mode_btn.setIcon(get_svg_icon("clapperboard", "#ffffff", 13))
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
            self.movie_mode_btn.setText("Auto")
            self.movie_mode_btn.setIcon(get_svg_icon("clapperboard", "#ffffff", 13))
            self.status_label.setText("Notchgent • Idle")
            self.status_dot.setStyleSheet("color: #10b981;")


        self.remote_server.update_state(
            self.remote_server._state.get("status", "idle"),
            self.remote_server._state.get("action"),
            self.remote_server._state.get("workspace", ""),
            self.auto_movie_active,
            is_muted=self.is_muted
        )

    def toggle_mute(self):
        self.is_muted = not self.is_muted
        self.sound_mode = "silent" if self.is_muted else "beep"
        self._update_mute_ui()
        self._save_sound_preference()
        self.remote_server.update_state(
            self.remote_server._state.get("status", "idle"),
            self.remote_server._state.get("action"),
            self.remote_server._state.get("workspace", ""),
            self.auto_movie_active,
            is_muted=self.is_muted
        )
        return self.is_muted

    def _update_mute_ui(self):
        if not hasattr(self, "mute_btn"):
            return
        if self.is_muted:
            self.mute_btn.setIcon(get_svg_icon("volume_x", "#ef4444", 13))
            self.mute_btn.setToolTip("Unmute Sound / Beep (Alt+M)")
            self.mute_btn.setStyleSheet("""
                #MuteBtn {
                    background-color: rgba(239, 68, 68, 0.22);
                    border: 1px solid rgba(239, 68, 68, 0.55);
                    border-radius: 12px;
                    padding: 0;
                }
                #MuteBtn:hover {
                    background-color: rgba(239, 68, 68, 0.35);
                }
            """)
        else:
            self.mute_btn.setIcon(get_svg_icon("volume_2", "#ffffff", 13))
            self.mute_btn.setToolTip("Mute Sound / Beep (Alt+M)")
            self.mute_btn.setStyleSheet("""
                #MuteBtn {
                    background-color: rgba(255, 255, 255, 0.1);
                    border: 1px solid rgba(255, 255, 255, 0.18);
                    border-radius: 12px;
                    padding: 0;
                }
                #MuteBtn:hover {
                    background-color: rgba(255, 255, 255, 0.2);
                }
            """)

    def _save_sound_preference(self):
        config_path = os.path.join(SCRIPT_DIR, "config.json")
        try:
            cfg = {}
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
            cfg["sound"] = "silent" if self.is_muted else "beep"
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2)
        except Exception:
            pass

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
            self.movie_mode_btn.setText(f"{mins:02d}:{secs:02d}")

    def setup_hotkeys(self):
        if not PYNPUT_AVAILABLE:
            return

        def on_1():
            release_all_modifiers()
            QTimer.singleShot(60, self.on_approve_clicked)

        def on_2():
            release_all_modifiers()
            QTimer.singleShot(60, self.on_deny_clicked)

        def on_mute():
            release_all_modifiers()
            QTimer.singleShot(0, self.toggle_mute)

        try:
            hotkeys = {
                "<alt>+1": on_1,
                "<alt>+a": on_1,
                "<f8>": on_1,
                "<alt>+2": on_2,
                "<alt>+d": on_2,
                "<f9>": on_2,
                "<alt>+m": on_mute
            }
            self.listener = keyboard.GlobalHotKeys(hotkeys)
            self.listener.daemon = True
            self.listener.start()
        except Exception:
            pass

    def toggle_remote_dialog(self):
        if self.remote_dialog and self.remote_dialog.isVisible():
            self.remote_dialog.hide()
            return

        if not self.remote_dialog:
            self.remote_dialog = RemoteDialog()
            self.remote_dialog.rotate_requested.connect(self._on_rotate_remote_key)

        if not self.tunnel_manager.is_connected and not self.tunnel_manager.public_url:
            self.tunnel_manager.restart()

        pub_url = ""
        if self.tunnel_manager.public_url:
            pub_url = f"{self.tunnel_manager.public_url}/#token={self.remote_server.token}"
        local_url = f"http://{self.tunnel_manager.local_ip}:{self.remote_server.port}/#token={self.remote_server.token}"


        self.remote_dialog.set_tunnel_url(pub_url, local_url)
        self.remote_dialog.update_connection_count(self.remote_server.connected_devices_count)

        x = self.x() + (self.width() - self.remote_dialog.width()) // 2
        y = self.y() + self.height() + 8
        self.remote_dialog.move(x, y)
        self.remote_dialog.show()
        self.remote_dialog.raise_()

    def _on_rotate_remote_key(self):
        new_token = self.remote_server.rotate_token()
        # Force a fresh Cloudflare tunnel provision so a stale link is immediately repaired!
        self.tunnel_manager.restart()
        local_url = f"http://{self.tunnel_manager.local_ip}:{self.remote_server.port}/#token={new_token}"
        if self.remote_dialog:
            self.remote_dialog.set_tunnel_url("", local_url)

    def _on_tunnel_url_discovered(self, url: str):
        full_url = f"{url}/#token={self.remote_server.token}"
        local_url = f"http://{self.tunnel_manager.local_ip}:{self.remote_server.port}/#token={self.remote_server.token}"
        if self.remote_dialog:
            self.remote_dialog.set_tunnel_url(full_url, local_url)
        self.remote_mode_btn.setIcon(get_svg_icon("phone", "#34d399", 13))
        self.remote_mode_btn.setStyleSheet("""
            #RemoteModeBtn {
                background-color: rgba(16, 185, 129, 0.22);
                border: 1px solid rgba(16, 185, 129, 0.5);
                color: #34d399;
                border-radius: 12px;
                font-size: 11px;
                font-weight: 600;
                padding: 0 4px;
            }
        """)

    def _on_tunnel_status_changed(self, status: str):
        if self.remote_dialog:
            if status == "Connected":
                self.remote_dialog.status_pill.setText("Secure Tunnel Active")
                self.remote_dialog.status_pill.setStyleSheet("""
                    background-color: rgba(16, 185, 129, 0.14);
                    color: #34d399;
                    border: 1px solid rgba(16, 185, 129, 0.3);
                    border-radius: 10px;
                """)
            elif "reconnect" in status.lower() or "refresh" in status.lower():
                self.remote_dialog.status_pill.setText("Reconnecting tunnel...")
                self.remote_dialog.status_pill.setStyleSheet("""
                    background-color: rgba(245, 158, 11, 0.14);
                    color: #fbbf24;
                    border: 1px solid rgba(245, 158, 11, 0.3);
                    border-radius: 10px;
                """)
            elif status.startswith("Error") or status == "Offline":
                self.remote_dialog.status_pill.setText(status)


    def _sync_remote_devices(self):
        count = self.remote_server.connected_devices_count
        if self.remote_dialog and self.remote_dialog.isVisible():
            self.remote_dialog.update_connection_count(count)
        if count > 0:
            self.remote_mode_btn.setText(f"{count} Online")
            self.remote_mode_btn.setIcon(get_svg_icon("phone", "#34d399", 13))
            self.remote_mode_btn.setStyleSheet("""
                #RemoteModeBtn {
                    background-color: rgba(16, 185, 129, 0.25);
                    border: 1px solid rgba(16, 185, 129, 0.6);
                    color: #34d399;
                    border-radius: 12px;
                    font-size: 11px;
                    font-weight: 600;
                    padding: 0 4px;
                }
            """)
        elif self.tunnel_manager.public_url:
            self.remote_mode_btn.setText("Remote")
            self.remote_mode_btn.setIcon(get_svg_icon("phone", "#34d399", 13))
            self.remote_mode_btn.setStyleSheet("""
                #RemoteModeBtn {
                    background-color: rgba(16, 185, 129, 0.18);
                    border: 1px solid rgba(16, 185, 129, 0.4);
                    color: #34d399;
                    border-radius: 12px;
                    font-size: 11px;
                    font-weight: 600;
                    padding: 0 4px;
                }
            """)
        else:
            self.remote_mode_btn.setText("Remote")
            self.remote_mode_btn.setIcon(get_svg_icon("phone", "#ffffff", 13))


    def _handle_remote_action(self, key_str: str):
        if key_str == "1":
            self.on_approve_clicked()
        elif key_str == "2":
            self.on_deny_clicked()

    def _handle_remote_toggle_auto(self):
        self.movie_mode_btn.setChecked(not self.movie_mode_btn.isChecked())
        self.toggle_movie_mode()

    def _handle_remote_toggle_mute(self):
        self.toggle_mute()

    def closeEvent(self, event):
        set_keep_awake(False)
        if hasattr(self, "listener") and self.listener:
            try:
                self.listener.stop()
            except Exception:
                pass
        if self.remote_dialog:
            try:
                self.remote_dialog.close()
            except Exception:
                pass
        self.tunnel_manager.stop()
        self.remote_server.stop()
        super().closeEvent(event)


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
