#!/usr/bin/env python3
"""
Installer to register Notchgent PreToolUse hook into ~/.gemini/config/hooks.json.
"""

import os
import sys
import json
import argparse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BRIDGE_PATH = os.path.join(SCRIPT_DIR, "bridge.py").replace("/", "\\")
GLOBAL_CONFIG_DIR = os.path.expanduser("~/.gemini/config")
HOOKS_FILE = os.path.join(GLOBAL_CONFIG_DIR, "hooks.json")


def install():
    os.makedirs(GLOBAL_CONFIG_DIR, exist_ok=True)
    hooks_data = {}
    if os.path.exists(HOOKS_FILE):
        try:
            with open(HOOKS_FILE, "r", encoding="utf-8") as f:
                hooks_data = json.load(f)
        except Exception:
            hooks_data = {}

    python_exe = sys.executable.replace("/", "\\")
    cmd_str = f"{python_exe} {BRIDGE_PATH}"

    hooks_data["notchgent"] = {
        "enabled": True,
        "PreToolUse": [
            {
                "matcher": "run_command|replace_file_content|write_to_file",
                "hooks": [
                    {
                        "type": "command",
                        "command": cmd_str,
                        "timeout": 120
                    }
                ]
            }
        ]
    }

    with open(HOOKS_FILE, "w", encoding="utf-8") as f:
        json.dump(hooks_data, f, indent=2)

    print(f"Notchgent hook registered in: {HOOKS_FILE}")
    print(f"Command: {cmd_str}")


def uninstall():
    if not os.path.exists(HOOKS_FILE):
        print("No hooks.json found.")
        return
    try:
        with open(HOOKS_FILE, "r", encoding="utf-8") as f:
            hooks_data = json.load(f)
    except Exception:
        hooks_data = {}

    if "notchgent" in hooks_data:
        del hooks_data["notchgent"]
        with open(HOOKS_FILE, "w", encoding="utf-8") as f:
            json.dump(hooks_data, f, indent=2)
        print("Notchgent hook removed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--uninstall", action="store_true")
    args = parser.parse_args()
    if args.uninstall:
        uninstall()
    else:
        install()
