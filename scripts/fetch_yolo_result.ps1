param(
    [string]$BoardIp = "192.168.127.10",
    [string]$User = "sunrise",
    [string]$RemoteDir = "/home/sunrise/yolo_s100p_run",
    [string]$RemoteFile = "render_result.jpeg",
    [string]$LocalDir = "."
)

$remote = "${User}@${BoardIp}:${RemoteDir}/${RemoteFile}"
Write-Host "Fetching $remote"
scp $remote $LocalDir
