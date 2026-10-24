# Solo lettura: elenca i programmi accesi che Sky Go puo' scambiare per un registratore dello schermo. Non chiude e non cambia niente.
$sospetti = @{
  'GameBar'='Xbox Game Bar (registra lo schermo)'; 'GameBarPresenceWriter'='Xbox Game Bar'; 'XboxGameBarWidgets'='Xbox Game Bar';
  'obs64'='OBS'; 'obs32'='OBS'; 'Claude'='App Claude (puo'' vedere lo schermo)'; 'claude'='App Claude'; 'cowork'='Cowork';
  'PhoneExperienceHost'='Collegamento al telefono (Phone Link)'; 'YourPhone'='Collegamento al telefono';
  'lively'='Lively (sfondi animati)'; 'Lively'='Lively'; 'NVIDIA Share'='NVIDIA (registrazione)'; 'nvsphelper64'='NVIDIA (registrazione)'; 'NVIDIA Overlay'='NVIDIA overlay';
  'RadeonSoftware'='AMD (registrazione)'; 'Teams'='Teams'; 'ms-teams'='Teams'; 'Zoom'='Zoom'; 'Discord'='Discord'; 'AnyDesk'='AnyDesk (controllo remoto)';
  'TeamViewer'='TeamViewer (controllo remoto)'; 'tailscaled'='Tailscale'; 'tailscale-ipn'='Tailscale'; 'ScreenToGif'='ScreenToGif'; 'Snagit32'='Snagit'; 'SnippingTool'='Strumento di cattura'; 'ScreenClippingHost'='Cattura schermo';
  'sunshine'='Sunshine (streaming schermo)'; 'steamwebhelper'='Steam (puo'' fare streaming)'; 'RemoteDesktop'='Desktop remoto'; 'rdpclip'='Desktop remoto'; 'vncserver'='VNC'; 'python'='Python (anche Jarvis)'; 'pythonw'='Python (anche Jarvis)'; 'node'='Node (programma WhatsApp di Jarvis)'
}
$visti = @{}
Get-Process | ForEach-Object {
  if ($sospetti.ContainsKey($_.ProcessName) -and -not $visti.ContainsKey($_.ProcessName)) { $visti[$_.ProcessName] = $sospetti[$_.ProcessName] }
}
Write-Host ''
if ($visti.Count -eq 0) { Write-Host 'Non vedo programmi dell''elenco dei sospetti.' }
else { Write-Host 'Programmi accesi che Sky Go potrebbe scambiare per un registratore:'; $visti.GetEnumerator() | Sort-Object Name | ForEach-Object { Write-Host (' - ' + $_.Value + '   [' + $_.Name + ']') } }
Write-Host ''
Write-Host 'Altri programmi con una finestra aperta:'
Get-Process | Where-Object { $_.MainWindowTitle -ne '' } | Select-Object -ExpandProperty ProcessName -Unique | Sort-Object | ForEach-Object { Write-Host (' - ' + $_) }
