import win32gui
import win32process
import win32con
import psutil
import time
import pyautogui

def find_vscode_window():
    found = []
    def enum_cb(hwnd, extra):
        if win32gui.IsWindowVisible(hwnd) and not win32gui.IsIconic(hwnd):
            title = win32gui.GetWindowText(hwnd)
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            try:
                p = psutil.Process(pid)
                if "code" in p.name().lower() and title:
                    # Ignore tiny tool windows or popups
                    rect = win32gui.GetWindowRect(hwnd)
                    w = rect[2] - rect[0]
                    h = rect[3] - rect[1]
                    if w > 300 and h > 200:
                        found.append((hwnd, title, w * h))
            except Exception:
                pass
    win32gui.EnumWindows(enum_cb, None)
    if found:
        # Sort by area descending (main window is largest)
        found.sort(key=lambda x: x[2], reverse=True)
        return found[0][0], found[0][1]
    return None, None

def send_key_to_vscode(key_str="1"):
    hwnd, title = find_vscode_window()
    if not hwnd:
        print("VS Code window not found")
        return False
    print(f"Found VS Code: {title} (hwnd={hwnd})")
    prev_hwnd = win32gui.GetForegroundWindow()
    try:
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.04)
        pyautogui.press(key_str)
        pyautogui.press("enter")
        print(f"Sent '{key_str}' + Enter to VS Code")
    finally:
        if prev_hwnd and prev_hwnd != hwnd:
            try:
                win32gui.SetForegroundWindow(prev_hwnd)
            except Exception:
                pass
    return True

if __name__ == "__main__":
    send_key_to_vscode("1")
