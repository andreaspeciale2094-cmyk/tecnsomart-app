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

' Se Jarvis e' gia' acceso si apre subito la pagina; altrimenti lo si accende (nascosto) e si apre SUBITO una schermata di avvio che passa da sola a Jarvis quando e' pronto
indirizzo = "http://localhost:8000"
If Not acceso() Then
  sh.CurrentDirectory = cartella
  sh.Run """" & cartella & "\.venv\Scripts\python.exe"" -m uvicorn jarvis.server:app --port 8000", 0, False
  indirizzo = "file:///" & Replace(Replace(cartella, "\", "/"), " ", "%20") & "/scripts/avvio_jarvis.html"
End If

browser = ""
On Error Resume Next
browser = sh.RegRead("HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe\")
If browser = "" Then browser = sh.RegRead("HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe\")
If browser = "" Then browser = sh.RegRead("HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe\")
On Error GoTo 0
' tutto schermo vero (senza bordi, copre la barra di Windows): F11 o il pulsante nella barra di Jarvis per uscire; la barra di Jarvis in basso sostituisce quella di Windows
If browser <> "" Then
  sh.Run """" & browser & """ --start-fullscreen --app=" & indirizzo & " --user-data-dir=""" & cartella & "\memoria\finestra_jarvis"" --no-first-run", 1, False
Else
  sh.Run indirizzo, 1, False
End If
