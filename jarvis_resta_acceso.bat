@echo off
cd /d "%~dp0"
echo.
echo  JARVIS RESTA ACCESO CON IL COPERCHIO CHIUSO
echo  -------------------------------------------
echo  Cosa cambia (solo in questo PC, solo il tuo utente, nessun permesso speciale):
echo   - quando chiudi il coperchio il PC NON va piu' in sospensione: resta acceso e Jarvis continua a funzionare
echo   - alla corrente non va in sospensione da solo (resta acceso anche se non lo tocchi)
echo   - a batteria va in sospensione dopo 30 minuti di inattivita', per non scaricarla
echo.
echo  Attenzione: un portatile chiuso e acceso scalda e consuma. Tienilo appoggiato e alla corrente, mai dentro una borsa.
echo  "Arresta il sistema" spegne tutto come sempre.
echo  Per tornare come prima: jarvis_torna_normale.bat
echo.
set /p R=" Scrivi SI per continuare, qualsiasi altra cosa per annullare: "
if /i not "%R%"=="SI" (
  echo.
  echo Annullato. Non ho cambiato niente.
  pause
  exit /b 0
)
if not exist "memoria" mkdir "memoria"
if not exist "memoria\energia_prima.txt" (
  powershell -NoProfile -Command "$o=@(); foreach($p in @(@('SUB_BUTTONS','LIDACTION'),@('SUB_SLEEP','STANDBYIDLE'))){ $t=@((powercfg /query SCHEME_CURRENT $p[0] $p[1]) | Select-String '0x[0-9a-fA-F]{8}' -AllMatches | ForEach-Object { $_.Matches.Value }); $o+=[Convert]::ToInt32($t[-2],16); $o+=[Convert]::ToInt32($t[-1],16) }; ($o -join ' ') | Set-Content 'memoria\energia_prima.txt'"
)
if not exist "memoria\energia_prima.txt" (
  echo Non riesco a salvare le impostazioni attuali: non cambio niente.
  pause
  exit /b 1
)
powercfg /setacvalueindex SCHEME_CURRENT SUB_BUTTONS LIDACTION 0
powercfg /setdcvalueindex SCHEME_CURRENT SUB_BUTTONS LIDACTION 0
powercfg /setacvalueindex SCHEME_CURRENT SUB_SLEEP STANDBYIDLE 0
powercfg /setdcvalueindex SCHEME_CURRENT SUB_SLEEP STANDBYIDLE 1800
powercfg /setactive SCHEME_CURRENT
echo.
echo FATTO. Ora puoi chiudere il coperchio: Jarvis resta acceso e lo trovi dal telefono.
echo Le impostazioni di prima sono salvate in memoria\energia_prima.txt.
pause
