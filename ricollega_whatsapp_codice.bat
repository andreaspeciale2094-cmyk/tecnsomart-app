@echo off
rem Come ricollega_whatsapp.bat, ma con un CODICE da scrivere sul telefono invece del QR. JARVIS DEVE ESSERE SPENTO.
cd /d "%~dp0"
echo.
echo  COLLEGARE WHATSAPP CON UN CODICE
echo  Scrivi il tuo numero di telefono con il prefisso, senza + e senza spazi (esempio: 393331234567).
set /p NUM=" Numero: "
if "%NUM%"=="" exit /b 1
if exist "memoria\whatsapp\auth" (
  if not exist "memoria\_da_eliminare" mkdir "memoria\_da_eliminare"
  move "memoria\whatsapp\auth" "memoria\_da_eliminare\whatsapp_auth_%RANDOM%%RANDOM%" >nul 2>&1
)
cd /d "%~dp0whatsapp_helper"
if not exist node_modules\qrcode (
  echo Installo i componenti, ci vuole un minuto...
  call npm install --omit=dev
)
node server.js --collega --numero=%NUM%
pause
