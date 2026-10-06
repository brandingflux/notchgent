@echo off
if exist "%~dp0dist\Notchgent.exe" (
    start "" "%~dp0dist\Notchgent.exe"
) else (
    start "" pythonw "%~dp0notchgent.py"
)
