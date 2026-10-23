@echo off
rem Ricollega WhatsApp per scaricare tutta la storia dei messaggi (si fa una volta). JARVIS DEVE ESSERE SPENTO.
cd /d "%~dp0"
echo.
echo  RICOLLEGARE WHATSAPP (per leggere anche i messaggi vecchi)
echo  ----------------------------------------------------------
echo  1) Spegni Jarvis (icona "Spegni Jarvis").
echo  2) Sul telefono: WhatsApp - Impostazioni - Dispositivi collegati - tocca Jarvis - Esci.
echo  3) Premi un tasto qui: comparira' un codice da scansionare con il telefono.
echo  4) Dopo la scansione NON chiudere questa finestra finche' non vedi la scritta FATTO (puo' volerci qualche minuto).
echo  I vecchi dati del collegamento vengono messi in memoria\_da_eliminare (non si cancella niente).
echo.
pause
if exist "memoria\whatsapp\auth" (
  if not exist "memoria\_da_eliminare" mkdir "memoria\_da_eliminare"
  move "memoria\whatsapp\auth" "memoria\_da_eliminare\whatsapp_auth_%DATE:/=-%_%TIME::=-%" >nul 2>&1
  if exist "memoria\whatsapp\auth" (
    echo Non riesco a mettere da parte il vecchio collegamento: Jarvis e' ancora acceso? Spegnilo e riprova.
    pause
    exit /b 1
  )
)
call "%~dp03_collega_whatsapp.bat"
