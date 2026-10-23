' Jarvis come "sistema": al posto del desktop di Windows parte lui. Questo programma resta acceso e lo sorveglia:
'   - se Jarvis non risponde entro 2 minuti dall'accensione  -> compare il desktop normale di Windows (via d'uscita)
'   - se chiudi la finestra di Jarvis                        -> la riapre
'   - se Jarvis si spegne da solo                            -> prova a riaccenderlo; se non ci riesce, desktop normale di Windows
'   - se usi "Spegni Jarvis" (o il pulsante Windows)         -> desktop normale di Windows
Set fso = CreateObject("Scripting.FileSystemObject")
cartella = fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName))
Set sh = CreateObject("WScript.Shell")
flag = cartella & "\memoria\spegnimento_voluto.flag"
apri = "wscript.exe """ & cartella & "\scripts\apri_jarvis.vbs"""
If fso.FileExists(flag) Then fso.DeleteFile flag

Function acceso()
  On Error Resume Next
  Set h = CreateObject("MSXML2.ServerXMLHTTP.6.0")
  h.setTimeouts 500, 500, 500, 500
  h.open "GET", "http://127.0.0.1:8000/api/auth", False
  h.send
  acceso = (Err.Number = 0)
  On Error GoTo 0
End Function

Function finestraAperta()
  On Error Resume Next
  Set wmi = GetObject("winmgmts:\\.\root\cimv2")
  finestraAperta = (wmi.ExecQuery("SELECT ProcessId FROM Win32_Process WHERE CommandLine LIKE '%finestra_jarvis%'").Count > 0)
  If Err.Number <> 0 Then finestraAperta = True  ' se non riesco a controllare, non faccio niente
  On Error GoTo 0
End Function

Function explorerAttivo()
  On Error Resume Next
  Set wmi = GetObject("winmgmts:\\.\root\cimv2")
  explorerAttivo = (wmi.ExecQuery("SELECT ProcessId FROM Win32_Process WHERE Name='explorer.exe'").Count > 0)
  If Err.Number <> 0 Then explorerAttivo = False
  On Error GoTo 0
End Function

' Fa comparire il desktop normale di Windows (solo se non c'e' gia': altrimenti si aprirebbe una finestra "Questo PC")
Sub desktopWindows()
  If Not explorerAttivo() Then sh.Run "explorer.exe", 1, False
End Sub

' Chiede a Jarvis di tornare davanti a tutto schermo (solo da questo PC, con la chiave in memoria\chiudi.token)
Sub jarvisDavanti()
  On Error Resume Next
  chiave = Trim(fso.OpenTextFile(cartella & "\memoria\chiudi.token").ReadLine)
  Set h = CreateObject("MSXML2.ServerXMLHTTP.6.0")
  h.setTimeouts 1000, 1000, 2000, 2000
  h.open "POST", "http://127.0.0.1:8000/api/davanti", False
  h.setRequestHeader "x-chiudi", chiave
  h.send
  On Error GoTo 0
End Sub

' 1) accende Jarvis e la sua schermata
sh.Run apri, 0, False

' 2) aspetta che risponda (massimo 2 minuti), altrimenti desktop normale
pronto = False
inizio = Now
Do While DateDiff("s", inizio, Now) < 120
  If acceso() Then
    pronto = True
    Exit Do
  End If
  WScript.Sleep 1000
Loop
If Not pronto Then
  desktopWindows
  WScript.Quit
End If

' 2b) Il desktop di Windows serve a far partire le app (collegamenti, app dello Store, Steam...): parte DIETRO Jarvis, che resta davanti a tutto schermo
WScript.Sleep 6000
If Not explorerAttivo() Then sh.Run "explorer.exe", 1, False
For i = 1 To 3
  WScript.Sleep 3500
  jarvisDavanti
Next

' 3) sorveglia Jarvis
senzaFinestra = 0
giu = 0
Do
  WScript.Sleep 4000
  If fso.FileExists(flag) Then
    On Error Resume Next
    fso.DeleteFile flag
    On Error GoTo 0
    desktopWindows
    WScript.Quit
  End If
  If acceso() Then
    giu = 0
    If finestraAperta() Then senzaFinestra = 0 Else senzaFinestra = senzaFinestra + 1
    If senzaFinestra >= 2 Then
      sh.Run apri, 0, False
      senzaFinestra = 0
      WScript.Sleep 8000
    End If
  Else
    giu = giu + 1
    If giu = 3 Then
      sh.Run apri, 0, False
      WScript.Sleep 20000
    ElseIf giu >= 6 Then
      desktopWindows
      WScript.Quit
    End If
  End If
Loop
