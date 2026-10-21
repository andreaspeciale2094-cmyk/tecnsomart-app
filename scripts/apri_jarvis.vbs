' Apre Jarvis come una finestra "app" (senza barra degli indirizzi). Se Jarvis non e' acceso lo accende prima, nascosto: nessuna finestra nera.
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
  For i = 1 To 40
    WScript.Sleep 500
    If acceso() Then Exit For
  Next
End If

chrome = ""
On Error Resume Next
chrome = sh.RegRead("HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe\")
If chrome = "" Then chrome = sh.RegRead("HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe\")
On Error GoTo 0
If chrome <> "" Then
  sh.Run """" & chrome & """ --app=http://localhost:8000", 1, False
Else
  sh.Run "http://localhost:8000", 1, False
End If
