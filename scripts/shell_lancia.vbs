' Piccolo programma di avvio sicuro (viene copiato in %APPDATA%\JarvisShell): se la cartella di Jarvis non c'e' piu' o manca un file,
' parte subito il desktop normale di Windows, cosi' non si resta mai con lo schermo vuoto.
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")
base = sh.ExpandEnvironmentStrings("%APPDATA%") & "\JarvisShell"
cartella = ""
On Error Resume Next
cartella = Trim(fso.OpenTextFile(base & "\cartella.txt").ReadLine)
On Error GoTo 0
If cartella <> "" And fso.FileExists(cartella & "\scripts\shell_jarvis.vbs") And fso.FileExists(cartella & "\scripts\apri_jarvis.vbs") Then
  sh.Run "wscript.exe """ & cartella & "\scripts\shell_jarvis.vbs""", 0, True
Else
  sh.Run "explorer.exe", 1, False
End If
