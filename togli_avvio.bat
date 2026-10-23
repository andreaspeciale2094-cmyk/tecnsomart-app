@echo off
rem Toglie l'avvio automatico di Jarvis: la voce nell'elenco di avvio di Windows (solo la sua) e, se c'e' ancora, il vecchio collegamento
rem nella cartella "Esecuzione automatica" (che va in memoria\_da_eliminare, non viene cancellato).
set "CARTELLA=%~dp0"
set "TOLTO="
reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v Jarvis >nul 2>&1
if not errorlevel 1 (
  reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v Jarvis /f >nul 2>&1
  set "TOLTO=1"
)
if exist "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Jarvis.lnk" (
  if not exist "%CARTELLA%memoria\_da_eliminare" mkdir "%CARTELLA%memoria\_da_eliminare"
  move "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Jarvis.lnk" "%CARTELLA%memoria\_da_eliminare\Jarvis-avvio.lnk" >nul 2>&1
  set "TOLTO=1"
)
if defined TOLTO (echo FATTO. Jarvis non parte piu' da solo.) else (echo L'avvio automatico non era attivo.)
pause
