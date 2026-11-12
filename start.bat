@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Run install.bat first and wait for setup to finish.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -m streamlit run app.py
