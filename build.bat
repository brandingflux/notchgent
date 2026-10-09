@echo off
setlocal
cd /d "%~dp0"

echo ==============================================
echo Building Notchgent Standalone Executable (.exe)
echo ==============================================

:: Terminate running instance if any
taskkill /F /IM Notchgent.exe >nul 2>&1
timeout /t 1 /nobreak >nul 2>&1

:: Generate/ensure icon exists
if not exist "app_icon.ico" (
    echo Generating app_icon.ico...
    python make_icon.py
)

:: Compile with PyInstaller
python -m PyInstaller ^
    --name "Notchgent" ^
    --onefile ^
    --windowed ^
    --icon "app_icon.ico" ^
    --add-data "app_icon.ico;." ^
    --add-data "config.json;." ^
    --add-binary "bin/cloudflared.exe;bin" ^
    --hidden-import "pynput.keyboard._win32" ^
    --hidden-import "pynput.mouse._win32" ^
    --hidden-import "win32gui" ^
    --hidden-import "win32con" ^
    --hidden-import "win32api" ^
    --hidden-import "win32process" ^
    --hidden-import "qrcode" ^
    --hidden-import "qrcode.image.pil" ^
    --hidden-import "remote_server" ^
    --hidden-import "tunnel_manager" ^
    --hidden-import "remote_dialog" ^
    --clean ^
    notchgent.py

if %ERRORLEVEL% equ 0 (
    echo.
    echo ==============================================
    echo Build SUCCESSFUL!
    echo Output executable: dist\Notchgent.exe
    echo ==============================================
) else (
    echo.
    echo Build FAILED with error code %ERRORLEVEL%.
)

endlocal
