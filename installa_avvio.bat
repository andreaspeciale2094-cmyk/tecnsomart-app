@echo off
rem Fa partire Jarvis da solo, senza finestre, quando accendi il PC.
rem Mette un collegamento nella cartella "Esecuzione automatica" del tuo utente. Non cambia le impostazioni di Windows.
rem Per toglierlo: togli_avvio.bat
set "CARTELLA=%~dp0"
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:APPDATA+'\Microsoft\Windows\Start Menu\Programs\Startup\Jarvis.lnk'); $s.TargetPath='%CARTELLA%scripts\jarvis_nascosto.vbs'; $s.WorkingDirectory='%CARTELLA%'; $s.Save()"
if exist "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Jarvis.lnk" (
  echo.
  echo FATTO. Da ora Jarvis parte da solo, senza finestre, quando accendi il PC.
  echo Per spegnerlo senza finestra: spegni_jarvis.bat
) else (
  echo.
  echo Non sono riuscito a creare il collegamento.
)
pause
