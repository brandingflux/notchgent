@echo off
setlocal
cd /d "%~dp0"

echo ==============================================
echo Building Notchgent Standalone Executable (.exe)
echo ==============================================

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
    --hidden-import "pynput.keyboard._win32" ^
    --hidden-import "pynput.mouse._win32" ^
    --hidden-import "win32gui" ^
    --hidden-import "win32con" ^
    --hidden-import "win32api" ^
    --hidden-import "win32process" ^
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
