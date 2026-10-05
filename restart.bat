@echo off
if exist "%~dp0.notchgent.pid" (
    for /f %%i in (%~dp0.notchgent.pid) do taskkill /F /PID %%i 2>nul
)
taskkill /F /IM pythonw.exe 2>nul
ping 127.0.0.1 -n 2 >nul
start "" pythonw "%~dp0notchgent.py"
echo Notchgent restarted!
