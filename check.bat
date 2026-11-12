@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Run install.bat first and wait for setup to finish.
    pause
    exit /b 1
)

echo Running automated tests...
set PYTHONDONTWRITEBYTECODE=1
".venv\Scripts\python.exe" -m pytest -p no:cacheprovider -v
if errorlevel 1 goto failed

echo Checking Python syntax...
".venv\Scripts\python.exe" scripts\check_syntax.py
if errorlevel 1 goto failed

echo Checking dependencies...
".venv\Scripts\python.exe" -m pip check
if errorlevel 1 goto failed

echo.
echo All checks passed.
pause
exit /b 0

:failed
echo.
echo Checks failed. Copy the output so it can be reviewed.
pause
exit /b 1
