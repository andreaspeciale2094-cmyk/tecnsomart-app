@echo off
cd /d "%~dp0"
echo.
echo  TORNA COME PRIMA (coperchio e sospensione)
echo  ------------------------------------------
if not exist "memoria\energia_prima.txt" (
  echo Non trovo le impostazioni di prima: forse non hai mai usato jarvis_resta_acceso.bat. Non cambio niente.
  pause
  exit /b 0
)
set /p V=<"memoria\energia_prima.txt"
for /f "tokens=1-4" %%a in ("%V%") do (
  powercfg /setacvalueindex SCHEME_CURRENT SUB_BUTTONS LIDACTION %%a
  powercfg /setdcvalueindex SCHEME_CURRENT SUB_BUTTONS LIDACTION %%b
  powercfg /setacvalueindex SCHEME_CURRENT SUB_SLEEP STANDBYIDLE %%c
  powercfg /setdcvalueindex SCHEME_CURRENT SUB_SLEEP STANDBYIDLE %%d
)
powercfg /setactive SCHEME_CURRENT
if not exist "memoria\_da_eliminare" mkdir "memoria\_da_eliminare"
move /y "memoria\energia_prima.txt" "memoria\_da_eliminare\energia_prima_%RANDOM%.txt" >nul
echo.
echo FATTO. Coperchio e sospensione sono tornati come prima.
pause
