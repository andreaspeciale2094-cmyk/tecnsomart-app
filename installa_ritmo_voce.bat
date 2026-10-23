@echo off
rem Installa il piccolo programma che fa muovere la sfera a tempo con la voce (una volta sola, pochi MB). Serve internet.
"%~dp0.venv\Scripts\python.exe" -m pip install "miniaudio>=1.60"
if errorlevel 1 (
  echo.
  echo Qualcosa non e' andato. Controlla di essere connesso a internet e riprova.
) else (
  echo.
  echo FATTO. Ora spegni e riaccendi Jarvis: la sfera si muove a tempo con la voce.
)
pause
