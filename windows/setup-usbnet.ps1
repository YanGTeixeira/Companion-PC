# R36S PC Companion - configura o IP do adaptador USB (NCM) no Windows 11
# Rode como Administrador:  powershell -ExecutionPolicy Bypass -File setup-usbnet.ps1

$PcIp   = "10.55.0.1"
$R36sIp = "10.55.0.2"
$Mac    = "02-36-53-00-00-01"   # host_addr definido no companion-usbnet.sh

$nic = Get-NetAdapter | Where-Object { $_.MacAddress -eq $Mac -or $_.InterfaceDescription -match "NCM|UsbNcm|RNDIS" } |
       Select-Object -First 1

if (-not $nic) {
    Write-Host "Adaptador do R36S não encontrado. Conecte o cabo e rode 'companion-usbnet.sh up' no R36S." -ForegroundColor Red
    Get-NetAdapter | Format-Table Name, InterfaceDescription, MacAddress, Status
    exit 1
}

Write-Host "Adaptador: $($nic.Name) - $($nic.InterfaceDescription)"
Set-NetIPInterface -InterfaceIndex $nic.ifIndex -Dhcp Disabled -ErrorAction SilentlyContinue
Get-NetIPAddress -InterfaceIndex $nic.ifIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Remove-NetIPAddress -Confirm:$false -ErrorAction SilentlyContinue
New-NetIPAddress -InterfaceIndex $nic.ifIndex -IPAddress $PcIp -PrefixLength 24 | Out-Null
# Rede privada (evita bloqueios de firewall de rede pública)
Set-NetConnectionProfile -InterfaceIndex $nic.ifIndex -NetworkCategory Private -ErrorAction SilentlyContinue

Start-Sleep 1
if (Test-Connection $R36sIp -Count 2 -Quiet) {
    Write-Host "OK: R36S responde em $R36sIp" -ForegroundColor Green
} else {
    Write-Host "Sem resposta de $R36sIp ainda (o firewall do R36S ou o gadget pode não estar ativo)." -ForegroundColor Yellow
}
