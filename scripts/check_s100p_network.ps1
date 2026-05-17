param(
    [string]$BoardIp = "192.168.127.10"
)

Write-Host "Checking S100P network: $BoardIp"

Write-Host "`n[1] Ping"
ping $BoardIp

Write-Host "`n[2] SSH port"
Test-NetConnection $BoardIp -Port 22

Write-Host "`n[3] Local IPv4 interfaces"
Get-NetIPConfiguration |
    Select-Object InterfaceAlias, IPv4Address, IPv4DefaultGateway |
    Format-List
