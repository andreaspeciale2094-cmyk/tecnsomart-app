@echo off
rem All'accensione del PC parte Jarvis (nascosto) e apre la sua finestra, che e' il tuo "desktop" finche' non apri altri programmi.
rem Mette un collegamento nella cartella "Esecuzione automatica" del tuo utente. Non cambia le impostazioni di Windows.
rem Per toglierlo: togli_avvio.bat
set "CARTELLA=%~dp0"
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:APPDATA+'\Microsoft\Windows\Start Menu\Programs\Startup\Jarvis.lnk'); $s.TargetPath='%CARTELLA%scripts\apri_jarvis.vbs'; $s.WorkingDirectory='%CARTELLA%'; $s.Save()"
if exist "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Jarvis.lnk" (
  echo.
  echo FATTO. Da ora, quando accendi il PC, parte Jarvis e si apre la sua finestra.
  echo Per spegnerlo senza finestra: spegni_jarvis.bat
) else (
  echo.
  echo Non sono riuscito a creare il collegamento.
)
pause
