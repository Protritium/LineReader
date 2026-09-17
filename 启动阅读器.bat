@echo off
cd /d "%~dp0"
where pythonw >nul 2>nul
if %errorlevel% equ 0 (
    start "" pythonw reader.py
) else (
    py reader.py
    pause
)
