@echo off
rem Toglie l'avvio automatico di Jarvis (il collegamento va in memoria\_da_eliminare, non viene cancellato).
if not exist "%~dp0memoria\_da_eliminare" mkdir "%~dp0memoria\_da_eliminare"
move "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Jarvis.lnk" "%~dp0memoria\_da_eliminare\Jarvis-avvio.lnk" >nul 2>&1
if errorlevel 1 (echo L'avvio automatico non era attivo.) else (echo FATTO. Jarvis non parte piu' da solo.)
pause
