param(
    [string]$BoardIp = "192.168.127.10",
    [string]$User = "sunrise",
    [string]$RemoteDir = "/home/sunrise/yolo_s100p_run",
    [string]$RemoteFile = "render_result.jpeg",
    [string]$LocalDir = ".",
    [switch]$Force
)

if (-not (Get-Command scp -ErrorAction SilentlyContinue)) {
    throw "scp was not found. Install OpenSSH Client or run from a shell that provides scp."
}

if (-not (Get-Command ssh -ErrorAction SilentlyContinue)) {
    throw "ssh was not found. Install OpenSSH Client or run from a shell that provides ssh."
}

if (-not (Test-Path -LiteralPath $LocalDir)) {
    New-Item -ItemType Directory -Force -Path $LocalDir | Out-Null
}

$remotePath = "$RemoteDir/$RemoteFile"
$remoteTarget = "${User}@${BoardIp}"

Write-Host "Checking remote file ${remoteTarget}:$remotePath"
ssh $remoteTarget "test -f '$remotePath'"
if ($LASTEXITCODE -ne 0) {
    throw "Remote file does not exist: ${remoteTarget}:$remotePath"
}

$localPath = Join-Path $LocalDir $RemoteFile
if ((Test-Path -LiteralPath $localPath) -and -not $Force) {
    throw "Local file already exists: $localPath. Use -Force to overwrite."
}

$remote = "${User}@${BoardIp}:${RemoteDir}/${RemoteFile}"
Write-Host "Fetching $remote"
scp $remote $LocalDir
if ($LASTEXITCODE -ne 0) {
    throw "scp failed with exit code $LASTEXITCODE"
}
