' Spegne Jarvis con calma, senza finestre nere: prima salva le cose che durano.
Set fso = CreateObject("Scripting.FileSystemObject")
cartella = fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName))
Set sh = CreateObject("WScript.Shell")
sh.Run """" & cartella & "\.venv\Scripts\python.exe"" """ & cartella & "\scripts\spegni_jarvis.py""", 0, True
MsgBox "Jarvis si sta spegnendo.", 64, "Jarvis"
