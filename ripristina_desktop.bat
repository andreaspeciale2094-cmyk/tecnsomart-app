@echo off
rem Rimette il desktop normale di Windows (toglie Jarvis al posto del desktop) e Jarvis torna a partire dall'elenco di avvio, come prima.
set "CARTELLA=%~dp0"
reg delete "HKCU\Software\Microsoft\Windows NT\CurrentVersion\Winlogon" /v Shell /f >nul 2>&1
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v Jarvis /t REG_SZ /d "wscript.exe \"%CARTELLA%scripts\apri_jarvis.vbs\"" /f >nul 2>&1
if exist "%CARTELLA%memoria\spegnimento_voluto.flag" del "%CARTELLA%memoria\spegnimento_voluto.flag" >nul 2>&1
echo.
echo FATTO. Al prossimo accesso a Windows torna il desktop normale; Jarvis parte da solo come prima.
echo (Se vuoi anche l'avvio senza Jarvis: togli_avvio.bat)
pause
