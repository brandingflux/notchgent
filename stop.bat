@echo off
if exist "%~dp0.notchgent.pid" (
    for /f %%i in (%~dp0.notchgent.pid) do taskkill /F /PID %%i 2>nul
    del "%~dp0.notchgent.pid" 2>nul
)
taskkill /F /IM Notchgent.exe 2>nul
taskkill /F /IM pythonw.exe 2>nul
echo Notchgent stopped.
pause
