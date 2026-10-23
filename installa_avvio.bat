@echo off
rem All'accensione del PC parte Jarvis (nascosto) e apre subito la sua schermata, che e' il tuo "desktop" finche' non apri altri programmi.
rem Windows avvia i programmi della cartella "Esecuzione automatica" con un ritardo (a volte minuti). Qui invece Jarvis si mette nell'elenco
rem che Windows avvia SUBITO dopo l'accesso (solo per il tuo utente, senza permessi da amministratore). Non cambia altre impostazioni di Windows.
rem Il vecchio collegamento nella cartella "Esecuzione automatica", se c'e', viene spostato in memoria\_da_eliminare (altrimenti Jarvis partirebbe due volte).
rem Per toglierlo: togli_avvio.bat
set "CARTELLA=%~dp0"
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v Jarvis /t REG_SZ /d "wscript.exe \"%CARTELLA%scripts\apri_jarvis.vbs\"" /f >nul 2>&1
if errorlevel 1 (
  echo.
  echo Non sono riuscito a impostare l'avvio automatico.
  pause
  exit /b 1
)
if exist "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Jarvis.lnk" (
  if not exist "%CARTELLA%memoria\_da_eliminare" mkdir "%CARTELLA%memoria\_da_eliminare"
  move "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Jarvis.lnk" "%CARTELLA%memoria\_da_eliminare\Jarvis-avvio-vecchio.lnk" >nul 2>&1
)
echo.
echo FATTO. Da ora, appena accedi a Windows, parte Jarvis e si apre subito la sua schermata.
echo Per spegnerlo senza finestra: spegni_jarvis.bat   -   Per togliere l'avvio automatico: togli_avvio.bat
pause
