@echo off
cd /d "%~dp0"
echo Apro il sito Trenord in modo invisibile e guardo il tabellone di Gaggiano, ci vuole un minuto...
".venv\Scripts\python.exe" scripts\scopri_trenord.py Gaggiano
echo.
pause
