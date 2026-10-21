' Apre Jarvis a TUTTO SCHERMO, come un'app (senza barra degli indirizzi). Se Jarvis non e' acceso lo accende prima, nascosto: nessuna finestra nera.
Set fso = CreateObject("Scripting.FileSystemObject")
cartella = fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName))
Set sh = CreateObject("WScript.Shell")

Function acceso()
  On Error Resume Next
  Set h = CreateObject("MSXML2.ServerXMLHTTP.6.0")
  h.setTimeouts 500, 500, 500, 500
  h.open "GET", "http://127.0.0.1:8000/api/auth", False
  h.send
  acceso = (Err.Number = 0)
  On Error GoTo 0
End Function

If Not acceso() Then
  sh.CurrentDirectory = cartella
  sh.Run """" & cartella & "\.venv\Scripts\python.exe"" -m uvicorn jarvis.server:app --port 8000", 0, False
  For i = 1 To 120
    WScript.Sleep 500
    If acceso() Then Exit For
  Next
End If

browser = ""
On Error Resume Next
browser = sh.RegRead("HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe\")
If browser = "" Then browser = sh.RegRead("HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe\")
If browser = "" Then browser = sh.RegRead("HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe\")
On Error GoTo 0
' finestra massimizzata come un'app (F11 per il vero tutto schermo, Alt+F4 per chiudere la finestra)
If browser <> "" Then
  sh.Run """" & browser & """ --app=http://localhost:8000 --start-maximized", 1, False
Else
  sh.Run "http://localhost:8000", 1, False
End If
