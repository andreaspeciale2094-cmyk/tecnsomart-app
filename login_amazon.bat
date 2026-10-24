@echo off
cd /d "%~dp0"
echo.
echo  COLLEGAMENTO AD AMAZON (lo fai solo tu, una volta)
echo  Si apre Chrome: entra con il tuo account Amazon e la verifica in due passaggi.
echo  Jarvis non vede la password. Poi CHIUDI la finestra di Chrome.
echo.
".venv\Scripts\python.exe" scripts\login_amazon.py
pause
