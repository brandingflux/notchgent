#!/usr/bin/env python3
"""
Notchgent Bridge for Antigravity CLI Lifecycle Hooks.
Reads JSON from stdin, forwards to Notchgent HUD (port 5151),
and prints {"decision": "allow"|"deny"|"ask"} to stdout.
"""

import sys
import os
import json
import time
import urllib.request
import urllib.error

# Ensure UTF-8 I/O on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stdin.reconfigure(encoding="utf-8")
    except Exception:
        pass

BRIDGE_PORT = 5151
TIMEOUT_SECONDS = 60
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bridge.log")


def log(msg: str):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass


def main():
    try:
        # Read entire JSON payload from stdin
        raw_input = sys.stdin.read()
        if not raw_input or not raw_input.strip():
            log("Empty stdin received, falling back to ask")
            print(json.dumps({"decision": "ask"}))
            sys.stdout.flush()
            return

        payload = json.loads(raw_input)
    except Exception as e:
        log(f"Stdin JSON parse error: {e}")
        print(json.dumps({"decision": "ask", "reason": f"Bridge parse error: {e}"}))
        sys.stdout.flush()
        return

    # Check if this is a PreToolUse request (contains toolCall)
    tool_call = payload.get("toolCall")
    if not tool_call:
        log("No toolCall in payload, ignoring")
        print(json.dumps({}))
        sys.stdout.flush()
        return

    tool_name = tool_call.get("name", "unknown")
    log(f"Forwarding toolCall '{tool_name}' to Notchgent HUD on port {BRIDGE_PORT}")

    # Forward request to running Notchgent HUD
    try:
        req_data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"http://127.0.0.1:{BRIDGE_PORT}/request",
            data=req_data,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as response:
            res_body = response.read().decode("utf-8")
            result = json.loads(res_body)
            if result.get("decision") == "allow":
                result["permissionOverrides"] = ["*"]
            log(f"Notchgent HUD replied with: {result}")
            print(json.dumps(result))
            sys.stdout.flush()
    except (urllib.error.URLError, ConnectionRefusedError) as e:
        log(f"Notchgent HUD connection failed: {e}. Falling back to terminal prompt.")
        print(json.dumps({
            "decision": "ask",
            "reason": "Notchgent HUD is not running. Falling back to terminal prompt."
        }))
        sys.stdout.flush()
    except Exception as e:
        log(f"Bridge error/timeout: {e}. Falling back to terminal prompt.")
        print(json.dumps({
            "decision": "ask",
            "reason": f"Notchgent fallback: {e}"
        }))
        sys.stdout.flush()


if __name__ == "__main__":
    main()
