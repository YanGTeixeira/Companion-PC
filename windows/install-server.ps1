# R36S PC Companion - instala o servidor no Windows e faz ele iniciar com o logon.
# Uso (não precisa de Administrador):
#   powershell -ExecutionPolicy Bypass -File install-server.ps1
param([string]$Source = $PSScriptRoot)

$Dest = Join-Path $env:USERPROFILE "r36s-companion\server"
New-Item -ItemType Directory -Force -Path $Dest | Out-Null
Copy-Item (Join-Path $Source "server\*.py") $Dest -Force
# App do celular (servido pelo próprio servidor na porta 8770)
New-Item -ItemType Directory -Force -Path (Join-Path $Dest "web") | Out-Null
Copy-Item (Join-Path $Source "server\web\*") (Join-Path $Dest "web") -Recurse -Force

Write-Host "Instalando dependências..."
py -3 -m pip install --user --disable-pip-version-check -q --no-warn-script-location `
    websockets psutil pillow pycaw comtypes pystray qrcode `
    winrt-runtime winrt-Windows.Media.Control winrt-Windows.Foundation `
    winrt-Windows.Foundation.Collections winrt-Windows.Storage.Streams `
    winrt-Windows.UI.Notifications winrt-Windows.UI.Notifications.Management winrt-Windows.ApplicationModel

# pythonw = sem janela de console
$pyw = (py -3 -c "import sys, pathlib; print(pathlib.Path(sys.executable).with_name('pythonw.exe'))").Trim()
$script = Join-Path $Dest "companion_server.py"

$sh = New-Object -ComObject WScript.Shell
function New-Shortcut($lnk) {
    $s = $sh.CreateShortcut($lnk)
    $s.TargetPath = $pyw
    $s.Arguments = "`"$script`""
    $s.WorkingDirectory = $Dest
    $s.Description = "R36S PC Companion - servidor (ícone na bandeja)"
    $s.Save()
    Write-Host "Atalho: $lnk"
}
# Inicia junto com o Windows (sem janela, só o ícone na bandeja)
New-Shortcut (Join-Path ([Environment]::GetFolderPath("Startup")) "R36S PC Companion.lnk")
# Menu Iniciar: abrir pelo menu mostra o painel (ou inicia o servidor se estiver parado)
New-Shortcut (Join-Path ([Environment]::GetFolderPath("Programs")) "R36S PC Companion.lnk")

# Reinicia o servidor
$old = Get-CimInstance Win32_Process |
    Where-Object { $_.ProcessId -ne $PID -and $_.Name -match '^(py|pythonw?)\.exe$' -and $_.CommandLine -match 'companion_server\.py' }
$old | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep 1
# Processos abertos como Administrador não mostram a linha de comando e não podem ser fechados daqui
$busy = Get-NetTCPConnection -State Listen -LocalPort 8765 -ErrorAction SilentlyContinue
if ($busy) {
    Write-Warning "A porta 8765 ainda está em uso pelo processo $($busy.OwningProcess -join ', ') (provavelmente um servidor antigo aberto como Administrador)."
    Write-Warning "Feche-o pelo Gerenciador de Tarefas ou rode, como Admin: Stop-Process -Id $($busy.OwningProcess -join ',')"
}
Start-Process -FilePath $pyw -ArgumentList "`"$script`"" -WorkingDirectory $Dest
Start-Sleep 3
Get-Content (Join-Path $Dest "companion-server.log") -Tail 3
Write-Host "Token do R36S: veja 'token' em $Dest\config.json"
Write-Host "Celular: abra o painel (ícone na bandeja) e escaneie o QR code. Uma vez, como Admin: windows\setup-android.ps1"
