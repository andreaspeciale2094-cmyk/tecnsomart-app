@echo off
rem Prova di collegamento WhatsApp con la versione 6.7.24 della libreria (la "vecchia stabile"). JARVIS DEVE ESSERE SPENTO.
rem Non cambia package.json: se non funziona, per tornare alla versione di prima basta cancellare la cartella whatsapp_helper\node_modules e rifare 3_collega_whatsapp.bat.
cd /d "%~dp0whatsapp_helper"
echo Installo la versione 6.7.24, un minuto...
call npm install @whiskeysockets/baileys@6.7.24 --no-save --omit=dev
if errorlevel 1 (
  echo Non sono riuscito a installarla. Controlla internet e riprova.
  pause
  exit /b 1
)
echo.
node server.js --collega
pause
