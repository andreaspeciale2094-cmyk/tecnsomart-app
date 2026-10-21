' Avvia Jarvis senza finestre (usato dall'avvio automatico con Windows). Non cambia nessuna impostazione.
Set fso = CreateObject("Scripting.FileSystemObject")
cartella = fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName))
Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = cartella
sh.Run """" & cartella & "\.venv\Scripts\python.exe"" -m uvicorn jarvis.server:app --port 8000", 0, False
