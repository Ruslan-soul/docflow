@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

py -3.13 --version >nul 2>&1
if errorlevel 1 (
    echo Python 3.13 was not found.
    echo Install Python 3.13 with the Python Launcher, then run this file again.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating the project environment...
    py -3.13 -m venv .venv
    if errorlevel 1 goto failed
)

echo Installing dependencies. An internet connection is required...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install -r requirements-dev.txt
if errorlevel 1 goto failed

echo.
echo Installation complete. Run start.bat to open DocFlow.
pause
exit /b 0

:failed
echo.
echo Installation failed. Check your internet connection and try again.
pause
exit /b 1
