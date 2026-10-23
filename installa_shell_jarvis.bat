@echo off
echo.
echo  JARVIS AL POSTO DEL DESKTOP DI WINDOWS
echo  --------------------------------------
echo  Da ora, quando accedi a Windows, al posto del desktop (barra, menu Start, icone) parte SOLO Jarvis a tutto schermo.
echo.
echo  Cosa cambia:
echo   - non c'e' piu' la barra di Windows, il menu Start, l'orologio e le icone vicino all'orologio (Wi-Fi, Bluetooth, notifiche)
echo   - Jarvis ha gia' la sua barra, la ricerca, le app e il pulsante "Windows" per tornare al desktop normale
echo   - i programmi che Windows avvia da soli all'accesso (OneDrive e simili) non partono finche' non torna il desktop normale
echo.
echo  Le vie d'uscita:
echo   - se Jarvis non parte entro 2 minuti, o si spegne, torna da solo il desktop normale
echo   - "Spegni Jarvis" e il pulsante "Windows" nella barra di Jarvis riportano il desktop normale
echo   - per rimettere tutto com'era: ripristina_desktop.bat
echo   - se resti con lo schermo vuoto: premi Ctrl+Alt+Canc, scegli Gestione attivita', "Esegui nuova attivita", scrivi explorer.exe
echo.
echo  Questa e' una modifica a un'impostazione di accensione di Windows (solo per il tuo utente, senza permessi da amministratore).
set /p R=" Scrivi SI per continuare, qualsiasi altra cosa per annullare: "
if /i not "%R%"=="SI" (
  echo.
  echo Annullato. Non ho cambiato niente.
  pause
  exit /b 0
)
set "CARTELLA=%~dp0"
if not exist "%CARTELLA%scripts\shell_jarvis.vbs" (
  echo Manca scripts\shell_jarvis.vbs: non cambio niente.
  pause
  exit /b 1
)
set "BASE=%APPDATA%\JarvisShell"
if not exist "%BASE%" mkdir "%BASE%"
copy /y "%CARTELLA%scripts\shell_lancia.vbs" "%BASE%\shell_lancia.vbs" >nul
> "%BASE%\cartella.txt" echo %CARTELLA:~0,-1%
reg add "HKCU\Software\Microsoft\Windows NT\CurrentVersion\Winlogon" /v Shell /t REG_SZ /d "wscript.exe \"%BASE%\shell_lancia.vbs\"" /f >nul 2>&1
if errorlevel 1 (
  echo.
  echo Non sono riuscito a impostarlo. Non e' cambiato niente.
  pause
  exit /b 1
)
rem Con Jarvis al posto del desktop l'elenco di avvio di Windows non viene letto; lo si toglie per non aprirlo due volte quando torna il desktop normale.
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v Jarvis /f >nul 2>&1
echo.
echo FATTO. Al prossimo accesso a Windows (esci e rientra, oppure riavvia) partira' Jarvis al posto del desktop.
echo Per tornare come prima: ripristina_desktop.bat
pause
