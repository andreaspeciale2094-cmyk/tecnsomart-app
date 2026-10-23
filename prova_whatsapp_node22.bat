@echo off
rem Prova di collegamento WhatsApp con un Node 22 "portatile": si scarica in memoria\node22 e non cambia niente nel PC.
rem JARVIS DEVE ESSERE SPENTO e non devono esserci altre finestre nere aperte.
cd /d "%~dp0"
set "ND=%~dp0memoria\node22\node-v22.12.0-win-x64"
if not exist "%ND%\node.exe" (
  echo Scarico Node 22 portatile ^(circa 30 MB^), un momento...
  if not exist "memoria\node22" mkdir "memoria\node22"
  powershell -NoProfile -Command "Invoke-WebRequest -Uri 'https://nodejs.org/dist/v22.12.0/node-v22.12.0-win-x64.zip' -OutFile 'memoria\node22\node22.zip'; Expand-Archive -Path 'memoria\node22\node22.zip' -DestinationPath 'memoria\node22' -Force"
)
if not exist "%ND%\node.exe" (
  echo Non sono riuscito a scaricare Node 22. Controlla internet e riprova.
  pause
  exit /b 1
)
echo.
"%ND%\node.exe" --version
cd /d "%~dp0whatsapp_helper"
"%ND%\node.exe" server.js --collega
pause
