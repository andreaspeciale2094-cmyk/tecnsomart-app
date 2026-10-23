@echo off
rem Installa il programma che apre il sito Trenord in modo invisibile (usa il tuo Chrome o Edge, non scarica altri browser). Serve internet.
"%~dp0.venv\Scripts\python.exe" -m pip install playwright
if errorlevel 1 (
  echo.
  echo Qualcosa non e' andato. Controlla internet e riprova.
) else (
  echo.
  echo FATTO. Ora fai doppio clic su scopri_trenord.bat.
)
pause
