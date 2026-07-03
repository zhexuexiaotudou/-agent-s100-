param(
    [string]$BoardIp = "192.168.127.10",
    [int]$SshPort = 22
)

Write-Host "Checking S100P network: $BoardIp"

Write-Host "`n[1] Ping"
$pingOk = Test-Connection -ComputerName $BoardIp -Count 2 -Quiet
if ($pingOk) {
    Write-Host "Ping: OK"
} else {
    Write-Host "Ping: FAILED" -ForegroundColor Red
}

Write-Host "`n[2] SSH port"
$ssh = Test-NetConnection $BoardIp -Port $SshPort
$ssh | Format-List ComputerName, RemoteAddress, RemotePort, InterfaceAlias, SourceAddress, TcpTestSucceeded

Write-Host "`n[3] Local IPv4 interfaces"
Get-NetIPConfiguration |
    Select-Object InterfaceAlias, IPv4Address, IPv4DefaultGateway |
    Format-List

if (-not $pingOk -or -not $ssh.TcpTestSucceeded) {
    Write-Host "S100P network check failed. Verify Ethernet port, static IPv4 settings, board IP, and SSH service." -ForegroundColor Red
    exit 1
}

Write-Host "S100P network check passed." -ForegroundColor Green
