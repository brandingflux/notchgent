#!/usr/bin/env python3
"""
Tunnel Manager for Notchgent.
Manages Cloudflare Quick Tunnel (cloudflared.exe), Named Tunnels, and Local LAN.
Features:
  - Perpetual background supervisor with automatic auto-restart
  - Active HTTP heartbeat health probe to detect stale Cloudflare edge drops
  - Zero-hang non-blocking stderr reader
  - Named Cloudflare Tunnel support via config.json (CLOUDFLARE_TUNNEL_TOKEN)
  - Seamless fallback to Local Wi-Fi (192.168.x.x)
"""

import os
import re
import sys
import json
import time
import socket
import atexit
import threading
import subprocess
import urllib.request
import urllib.error
from typing import Optional, Callable

if getattr(sys, "frozen", False):
    SCRIPT_DIR = os.path.dirname(sys.executable)
else:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def find_cloudflared_exe() -> str:
    """Resolve cloudflared.exe binary path across all dev and PyInstaller runtime layouts."""
    candidates = []
    # 1. PyInstaller bundled temp directory (_MEIPASS)
    if hasattr(sys, "_MEIPASS"):
        candidates.append(os.path.join(sys._MEIPASS, "bin", "cloudflared.exe"))
        candidates.append(os.path.join(sys._MEIPASS, "cloudflared.exe"))

    # 2. Executable folder (e.g. dist/ or installed location)
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        candidates.append(os.path.join(exe_dir, "bin", "cloudflared.exe"))
        candidates.append(os.path.join(exe_dir, "cloudflared.exe"))
        candidates.append(os.path.join(exe_dir, "..", "bin", "cloudflared.exe"))

    # 3. Project / source directory
    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.join(base_dir, "bin", "cloudflared.exe"))
    candidates.append(os.path.join(base_dir, "cloudflared.exe"))
    candidates.append(os.path.join(base_dir, "..", "bin", "cloudflared.exe"))

    # 4. Global PATH
    import shutil
    which_path = shutil.which("cloudflared")
    if which_path:
        candidates.append(which_path)

    for p in candidates:
        if p and os.path.isfile(p):
            return os.path.abspath(p)

    return os.path.join(base_dir, "bin", "cloudflared.exe")


def find_config_json() -> str:
    """Resolve config.json location across dev and bundled runtime."""
    candidates = []
    if hasattr(sys, "_MEIPASS"):
        candidates.append(os.path.join(sys._MEIPASS, "config.json"))
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        candidates.append(os.path.join(exe_dir, "config.json"))
        candidates.append(os.path.join(exe_dir, "..", "config.json"))
    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.join(base_dir, "config.json"))
    candidates.append(os.path.join(base_dir, "..", "config.json"))

    for p in candidates:
        if p and os.path.isfile(p):
            return os.path.abspath(p)
    return os.path.join(base_dir, "config.json")


CLOUDFLARED_EXE = find_cloudflared_exe()


def get_local_lan_ip() -> str:
    """Detect local Wi-Fi / LAN IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        # Connect to a public DNS IP (no packet sent) to determine local interface
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


class TunnelManager:
    """Perpetual supervisor for Cloudflare Quick Tunnel and Local LAN networking."""

    def __init__(
        self,
        local_port: int = 5151,
        on_url_ready: Optional[Callable[[str], None]] = None,
        on_status_change: Optional[Callable[[str], None]] = None
    ):
        self.local_port = local_port
        self.on_url_ready = on_url_ready
        self.on_status_change = on_status_change

        self.proc: Optional[subprocess.Popen] = None
        self.public_url: Optional[str] = None
        self.local_ip: str = get_local_lan_ip()
        self.is_running = False
        self.is_connected = False

        self._stop_requested = False
        self._restart_event = threading.Event()
        self._supervisor_thread: Optional[threading.Thread] = None

        # Check for named tunnel token in config.json or environment
        self.named_token: Optional[str] = None
        self.named_url: Optional[str] = None
        self._load_config_tunnel_settings()

        atexit.register(self.stop)

    def _load_config_tunnel_settings(self):
        """Read optional custom tunnel token or URL from config.json."""
        cfg_path = find_config_json()
        if os.path.exists(cfg_path):
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    self.named_token = cfg.get("tunnel_token") or os.environ.get("CLOUDFLARE_TUNNEL_TOKEN")
                    self.named_url = cfg.get("tunnel_url")
            except Exception:
                pass
        else:
            self.named_token = os.environ.get("CLOUDFLARE_TUNNEL_TOKEN")

    def is_available(self) -> bool:
        """Check if cloudflared binary is installed."""
        return os.path.isfile(find_cloudflared_exe())

    def start(self):
        """Start the supervisor thread."""
        if self.is_running:
            return

        self._stop_requested = False
        self.is_running = True
        self._restart_event.clear()

        self._supervisor_thread = threading.Thread(target=self._supervisor_loop, daemon=True)
        self._supervisor_thread.start()

    def restart(self):
        """Force an immediate restart of the tunnel."""
        self.public_url = None
        self.is_connected = False
        if self.on_status_change:
            self.on_status_change("Reconnecting tunnel...")
        self._restart_event.set()
        self._kill_proc()

    def _kill_proc(self):
        """Safely terminate the cloudflared process."""
        proc = self.proc
        self.proc = None
        if proc:
            try:
                proc.terminate()
                proc.wait(timeout=1.5)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

    def _probe_health(self) -> bool:
        """Probe the public URL through Cloudflare Edge to verify active reachability."""
        if not self.public_url:
            return False
        try:
            req = urllib.request.Request(
                f"{self.public_url}/api/health",
                headers={"User-Agent": "Notchgent-Tunnel-Watchdog/1.0"}
            )
            with urllib.request.urlopen(req, timeout=8.0) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass
        return False

    def _supervisor_loop(self):
        """Main loop that continuously maintains, monitors, and restarts the tunnel."""
        cloudflared_exe = find_cloudflared_exe()
        if not os.path.exists(cloudflared_exe):
            if self.on_status_change:
                self.on_status_change("cloudflared.exe missing")
            self.is_running = False
            return

        startupinfo = None
        if sys.platform == "win32":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0

        while self.is_running and not self._stop_requested:
            self._restart_event.clear()
            self.local_ip = get_local_lan_ip()
            self.is_connected = False

            if self.on_status_change:
                self.on_status_change("Starting tunnel...")

            if self.named_token:
                cmd = [
                    cloudflared_exe,
                    "tunnel",
                    "run",
                    "--token", self.named_token,
                    "--no-autoupdate"
                ]
            else:
                cmd = [
                    cloudflared_exe,
                    "tunnel",
                    "--url", f"http://127.0.0.1:{self.local_port}",
                    "--no-autoupdate",
                    "--retries", "10",
                    "--proxy-keepalive-timeout", "15m",
                    "--edge-ip-version", "auto"
                ]

            discovered_url = None
            url_discovered_event = threading.Event()

            try:
                # Merge stderr into stdout so reading a single stream never deadlocks OS pipe buffers!
                self.proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="ignore",
                    startupinfo=startupinfo
                )

                def _reader():
                    nonlocal discovered_url
                    try:
                        while self.proc and self.proc.poll() is None:
                            line = self.proc.stdout.readline()
                            if not line:
                                break
                            m = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line)
                            if m and not discovered_url:
                                discovered_url = m.group(0)
                                url_discovered_event.set()
                    except Exception:
                        pass

                reader_thread = threading.Thread(target=_reader, daemon=True)
                reader_thread.start()

                # For named tunnels with custom URL:
                if self.named_token and self.named_url:
                    discovered_url = self.named_url
                    url_discovered_event.set()

                # Wait up to 35 seconds for URL discovery
                url_discovered_event.wait(timeout=35.0)

                if discovered_url and not self._restart_event.is_set() and not self._stop_requested:
                    self.public_url = discovered_url
                    self.is_connected = True
                    if self.on_status_change:
                        self.on_status_change("Connected")
                    if self.on_url_ready:
                        self.on_url_ready(discovered_url)

                    # Initial grace period for Cloudflare edge DNS to propagate globally
                    self._restart_event.wait(timeout=18.0)

                    # --- Active Health Watchdog Loop ---
                    # Periodically probe the public URL every 30 seconds
                    consecutive_probe_failures = 0
                    while not self._stop_requested and not self._restart_event.is_set():
                        if self.proc is None or self.proc.poll() is not None:
                            # Process died
                            break

                        # Wait 30 seconds before next health probe
                        woken = self._restart_event.wait(timeout=30.0)
                        if woken or self._stop_requested:
                            break

                        # Probe health over Cloudflare edge
                        if self._probe_health():
                            consecutive_probe_failures = 0
                        else:
                            consecutive_probe_failures += 1
                            # If 4 consecutive probes fail (>= 120s of confirmed edge downtime)
                            if consecutive_probe_failures >= 4:
                                if self.on_status_change:
                                    self.on_status_change("Tunnel expired, refreshing...")
                                break

                else:
                    if not self._restart_event.is_set() and not self._stop_requested:
                        if self.on_status_change:
                            self.on_status_change("Tunnel timeout, retrying...")

            except Exception as e:
                if self.on_status_change and not self._stop_requested:
                    self.on_status_change(f"Tunnel error: {e}")
            finally:
                self.is_connected = False
                self._kill_proc()

            if not self._stop_requested:
                if self.on_status_change:
                    self.on_status_change("Reconnecting tunnel...")
                # Backoff before restarting
                time.sleep(2.0)

        self.is_running = False
        if self.on_status_change:
            self.on_status_change("Offline")

    def stop(self):
        """Cleanly terminate the tunnel process and supervisor."""
        self._stop_requested = True
        self.is_running = False
        self.is_connected = False
        self._restart_event.set()
        self._kill_proc()
        self.public_url = None
        if self.on_status_change:
            self.on_status_change("Stopped")
