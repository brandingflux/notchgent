#!/usr/bin/env python3
"""
Tunnel Manager for Notchgent.
Manages Cloudflare Quick Tunnel (cloudflared.exe) and Local LAN fallback.
Provides:
  - Automatic URL discovery (trycloudflare.com)
  - Local LAN IP detection (192.168.x.x)
  - Process lifecycle management and auto-recovery
"""

import os
import re
import sys
import time
import socket
import atexit
import threading
import subprocess
from typing import Optional, Callable

if getattr(sys, "frozen", False):
    SCRIPT_DIR = os.path.dirname(sys.executable)
else:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

BIN_DIR = os.path.join(SCRIPT_DIR, "bin")
CLOUDFLARED_EXE = os.path.join(BIN_DIR, "cloudflared.exe")


def get_local_lan_ip() -> str:
    """Detect local Wi-Fi / LAN IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        # Connect to a public DNS IP (no packet actually sent) to determine local routing interface
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


class TunnelManager:
    """Manages the background cloudflared quick tunnel."""

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
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_requested = False

        atexit.register(self.stop)

    def is_available(self) -> bool:
        """Check if cloudflared binary is installed."""
        return os.path.exists(CLOUDFLARED_EXE)

    def start(self):
        """Start the tunnel in background."""
        if self.is_running:
            return

        self._stop_requested = False
        self.is_running = True
        self.public_url = None

        if self.on_status_change:
            self.on_status_change("Starting tunnel...")

        self._monitor_thread = threading.Thread(target=self._run_tunnel, daemon=True)
        self._monitor_thread.start()

    def _run_tunnel(self):
        if not os.path.exists(CLOUDFLARED_EXE):
            if self.on_status_change:
                self.on_status_change("cloudflared.exe missing")
            self.is_running = False
            return

        cmd = [
            CLOUDFLARED_EXE,
            "tunnel",
            "--url", f"http://127.0.0.1:{self.local_port}",
            "--no-autoupdate"
        ]

        # Hide console window on Windows
        startupinfo = None
        if sys.platform == "win32":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0

        try:
            self.proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="ignore",
                startupinfo=startupinfo
            )

            # Read stderr to discover URL
            discovered_url = None
            start_time = time.time()

            while self.is_running and not self._stop_requested:
                line = self.proc.stderr.readline()
                if not line:
                    if self.proc.poll() is not None:
                        break
                    time.sleep(0.05)
                    continue

                # Look for trycloudflare.com URL pattern
                m = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line)
                if m and not discovered_url:
                    discovered_url = m.group(0)
                    self.public_url = discovered_url
                    if self.on_status_change:
                        self.on_status_change("Connected")
                    if self.on_url_ready:
                        self.on_url_ready(discovered_url)

                # Timeout after 25s if no URL discovered
                if not discovered_url and (time.time() - start_time) > 25:
                    if self.on_status_change:
                        self.on_status_change("Tunnel timeout")
                    break

        except Exception as e:
            if self.on_status_change:
                self.on_status_change(f"Error: {e}")
        finally:
            self.is_running = False
            if not self._stop_requested and self.on_status_change:
                self.on_status_change("Offline")

    def stop(self):
        """Cleanly terminate the tunnel process."""
        self._stop_requested = True
        self.is_running = False
        if self.proc:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=1.5)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass
            self.proc = None
        self.public_url = None
        if self.on_status_change:
            self.on_status_change("Stopped")
