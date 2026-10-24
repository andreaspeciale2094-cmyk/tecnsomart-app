@echo off
cd /d "%~dp0"
echo.
".venv\Scripts\python.exe" scripts\controlla_notizie.py
pause
