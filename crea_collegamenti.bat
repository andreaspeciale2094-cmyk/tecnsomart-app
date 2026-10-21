@echo off
rem Crea sul Desktop due collegamenti: "Jarvis" (lo apre, e lo accende nascosto se serve) e "Spegni Jarvis".
rem Non apre finestre nere e non cambia le impostazioni di Windows.
set "CARTELLA=%~dp0"
powershell -NoProfile -Command "$d=[Environment]::GetFolderPath('Desktop'); $w=New-Object -ComObject WScript.Shell; $a=$w.CreateShortcut($d+'\Jarvis.lnk'); $a.TargetPath='wscript.exe'; $a.Arguments='\"%CARTELLA%scripts\apri_jarvis.vbs\"'; $a.WorkingDirectory='%CARTELLA%'; $a.IconLocation='%CARTELLA%static\jarvis.ico'; $a.Save(); $b=$w.CreateShortcut($d+'\Spegni Jarvis.lnk'); $b.TargetPath='wscript.exe'; $b.Arguments='\"%CARTELLA%scripts\spegni_jarvis.vbs\"'; $b.WorkingDirectory='%CARTELLA%'; $b.IconLocation='%CARTELLA%static\jarvis.ico'; $b.Save()"
echo.
echo FATTO. Sul Desktop ci sono "Jarvis" e "Spegni Jarvis".
pause
