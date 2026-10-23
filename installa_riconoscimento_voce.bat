@echo off
rem Installa il piccolo programma che riconosce la tua voce (una volta sola, circa 15 MB). Serve internet.
rem Il modello della voce (26 MB) si scarica da solo la prima volta che impari la tua voce dalla pagina di Jarvis.
"%~dp0.venv\Scripts\python.exe" -m pip install "sherpa-onnx>=1.12"
if errorlevel 1 (
  echo.
  echo Qualcosa non e' andato. Controlla di essere connesso a internet e riprova.
) else (
  echo.
  echo FATTO. Ora spegni e riaccendi Jarvis, poi nella finestra del microfono premi "Impara la mia voce".
)
pause
