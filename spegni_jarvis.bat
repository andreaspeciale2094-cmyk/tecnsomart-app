@echo off
rem Spegne Jarvis (anche se e' nascosto) salvando prima le cose che durano.
cd /d "%~dp0"
.venv\Scripts\python.exe scripts\spegni_jarvis.py
pause
