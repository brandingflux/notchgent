#!/usr/bin/env python3
"""
Test script to simulate an Antigravity CLI PreToolUse hook invocation.
Runs bridge.py with sample toolCall data on stdin and prints the result.
"""

import subprocess
import json
import sys
import os

sample_request = {
    "conversationId": "test-session-123",
    "stepIdx": 4,
    "toolCall": {
        "name": "replace_file_content",
        "args": {
            "TargetFile": "C:/Projects/webapp/src/components/MoviePlayer.tsx",
            "Instruction": "Add playback speed controls (1.25x, 1.5x) and subtitles sync offset",
            "toolAction": "Updating video player controls"
        }
    },
    "workspacePaths": ["C:/Projects/webapp"]
}

def run_test():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    bridge_path = os.path.join(script_dir, "bridge.py")
    
    print("[Test] Sending simulated Antigravity tool request to bridge.py...")
    print(f"[Test] Payload:\n{json.dumps(sample_request, indent=2)}")
    
    proc = subprocess.Popen(
        [sys.executable, bridge_path],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    stdout, stderr = proc.communicate(input=json.dumps(sample_request))
    
    print("\n[Test] Bridge Response from Notchgent:")
    print(f"Stdout: {stdout.strip()}")
    if stderr:
        print(f"Stderr: {stderr.strip()}")

if __name__ == "__main__":
    run_test()
