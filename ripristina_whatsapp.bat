@echo off
rem Rimette il vecchio collegamento WhatsApp (quello messo da parte da ricollega_whatsapp.bat). JARVIS DEVE ESSERE SPENTO.
cd /d "%~dp0"
set "VECCHIO="
for /f "delims=" %%D in ('dir /b /ad /o-d "memoria\_da_eliminare\whatsapp_auth_*" 2^>nul') do (
  if not defined VECCHIO set "VECCHIO=%%D"
)
if not defined VECCHIO (
  echo Non trovo nessun vecchio collegamento in memoria\_da_eliminare.
  pause
  exit /b 1
)
echo Rimetto il collegamento: %VECCHIO%
if exist "memoria\whatsapp\auth" (
  move "memoria\whatsapp\auth" "memoria\_da_eliminare\whatsapp_auth_provato_%RANDOM%" >nul
)
move "memoria\_da_eliminare\%VECCHIO%" "memoria\whatsapp\auth" >nul
if exist "memoria\whatsapp\auth" (
  echo FATTO. Accendi Jarvis: WhatsApp dovrebbe funzionare come prima ^(se il telefono non l'ha scollegato^).
) else (
  echo Non sono riuscito: Jarvis e' ancora acceso? Spegnilo e riprova.
)
pause
