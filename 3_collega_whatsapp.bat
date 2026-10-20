@echo off
rem Collega WhatsApp a Jarvis (si fa una volta). Mostra un codice da scansionare con il telefono.
rem Prima chiudi Jarvis se e' acceso.
cd /d "%~dp0whatsapp_helper"
if not exist node_modules (
  echo Installo i componenti, ci vuole un minuto...
  call npm install --omit=dev
)
echo.
node server.js --collega
pause
