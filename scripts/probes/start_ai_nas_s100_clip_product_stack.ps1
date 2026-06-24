param(
  [string]$Python = (Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
  [string]$Workspace = "F:\Project\Digua",
  [string]$S100Host = "192.168.127.10",
  [string]$S100User = "sunrise",
  [string]$SshKey = (Join-Path $env:USERPROFILE ".ssh\s100p_linkcheck_ed25519"),
  [int]$ClipPort = 18182,
  [int]$VisionPort = 18183,
  [int]$PortalPort = 53306,
  [string]$OfficialManagerUrl = "",
  [switch]$RestartPortal,
  [switch]$RestartClipGateway,
  [switch]$RestartVisionGateway
)

$ErrorActionPreference = "Stop"

function Invoke-S100 {
  param([string]$Command)
  ssh -o BatchMode=yes -o ConnectTimeout=8 -i $SshKey "$S100User@$S100Host" $Command
}

function Test-HttpJson {
  param([string]$Url)
  try {
    return Invoke-RestMethod -Uri $Url -TimeoutSec 5
  } catch {
    return $null
  }
}

function Get-PortalLocalConfig {
  $configPath = Join-Path $Workspace "configs\openclaw_nas_portal.local.json"
  if (-not (Test-Path -LiteralPath $configPath)) {
    return $null
  }
  try {
    return Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
  } catch {
    Write-Warning "Failed to read portal local config: $configPath"
    return $null
  }
}

function Ensure-OfficialManagerTunnel {
  param([AllowNull()]$Route)
  if ($null -eq $Route -or $Route.mode -ne "ssh_local_forward") {
    return $null
  }
  $localPort = [int]$Route.local_port
  if ($localPort -le 0) {
    return $null
  }
  $existingTunnel = Get-NetTCPConnection -LocalPort $localPort -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($existingTunnel) {
    return Get-Process -Id $existingTunnel.OwningProcess -ErrorAction SilentlyContinue
  }

  $routeSshKey = if ($Route.ssh_key) { ([string]$Route.ssh_key).Replace("/", "\") } else { $SshKey }
  $routeUser = if ($Route.ssh_user) { [string]$Route.ssh_user } else { $S100User }
  $routeHost = if ($Route.ssh_host) { [string]$Route.ssh_host } else { $S100Host }
  $nasHost = [string]$Route.nas_host
  $nasPort = if ($Route.nas_http_port) { [int]$Route.nas_http_port } else { 8080 }
  if (-not $nasHost) {
    return $null
  }
  $forward = "127.0.0.1:${localPort}:${nasHost}:${nasPort}"
  $sshArgs = @(
    "-i", $routeSshKey,
    "-o", "BatchMode=yes",
    "-o", "ExitOnForwardFailure=yes",
    "-o", "ServerAliveInterval=30",
    "-N",
    "-L", $forward,
    "${routeUser}@${routeHost}"
  )
  $proc = Start-Process -FilePath "ssh.exe" -ArgumentList $sshArgs -WindowStyle Hidden -PassThru
  for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Milliseconds 250
    $listener = Get-NetTCPConnection -LocalPort $localPort -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($listener) {
      return $proc
    }
  }
  throw "Official NAS manager tunnel did not open on 127.0.0.1:$localPort"
}

$clipScript = Join-Path $Workspace "scripts\probes\ai_nas_s100_clip_embedding_gateway.py"
if (-not (Test-Path -LiteralPath $clipScript)) {
  throw "Missing CLIP gateway script: $clipScript"
}
$visionScript = Join-Path $Workspace "scripts\probes\ai_nas_s100_grounded_vision_gateway.py"
if (-not (Test-Path -LiteralPath $visionScript)) {
  throw "Missing grounded vision gateway script: $visionScript"
}

$portalLocalConfig = Get-PortalLocalConfig
$resolvedOfficialManagerUrl = $OfficialManagerUrl.Trim()
if (-not $resolvedOfficialManagerUrl -and $portalLocalConfig -and $portalLocalConfig.official_manager_url) {
  $resolvedOfficialManagerUrl = [string]$portalLocalConfig.official_manager_url
}
$officialTunnel = $null
if ($portalLocalConfig -and $portalLocalConfig.official_manager_route) {
  $officialTunnel = Ensure-OfficialManagerTunnel -Route $portalLocalConfig.official_manager_route
}

$clipHealthUrl = "http://${S100Host}:${ClipPort}/health"
$clipHealth = Test-HttpJson $clipHealthUrl
if ($RestartClipGateway -or -not $clipHealth -or -not $clipHealth.ready) {
  Write-Host "Starting S100 CLIP gateway on ${S100Host}:${ClipPort}"
  scp -o BatchMode=yes -o ConnectTimeout=8 -i $SshKey $clipScript "$S100User@${S100Host}:/tmp/ai_nas_s100_clip_embedding_gateway.py" | Out-Null
  if ($RestartClipGateway) {
    Invoke-S100 "pkill -f ai_nas_s100_clip_embedding_gateway.py || true" | Out-Null
  }
  Invoke-S100 "nohup python3 /tmp/ai_nas_s100_clip_embedding_gateway.py --bind 0.0.0.0 --port $ClipPort --model-dir /mnt/nas/openclaw/models/ai_nas_clip_vit_base_patch32 --model-id s100p-clip-vit-base-patch32 --eager-load > /tmp/ai_nas_s100_clip_embedding_gateway.log 2>&1 &" | Out-Null
  for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Seconds 2
    $clipHealth = Test-HttpJson $clipHealthUrl
    if ($clipHealth -and $clipHealth.ready) { break }
  }
}
if (-not $clipHealth -or -not $clipHealth.ready) {
  throw "S100 CLIP gateway not ready at $clipHealthUrl"
}

$visionHealthUrl = "http://${S100Host}:${VisionPort}/health"
$visionHealth = Test-HttpJson $visionHealthUrl
if ($RestartVisionGateway -or -not $visionHealth -or -not $visionHealth.ready) {
  Write-Host "Starting S100 grounded vision gateway on ${S100Host}:${VisionPort}"
  scp -o BatchMode=yes -o ConnectTimeout=8 -i $SshKey $visionScript "$S100User@${S100Host}:/tmp/ai_nas_s100_grounded_vision_gateway.py" | Out-Null
  if ($RestartVisionGateway) {
    Invoke-S100 "pkill -f ai_nas_s100_grounded_vision_gateway.py || true" | Out-Null
  }
  Invoke-S100 "nohup python3 /tmp/ai_nas_s100_grounded_vision_gateway.py --bind 0.0.0.0 --port $VisionPort --cache-root /tmp/ai_nas_s100_grounded_vision_gateway_runtime > /tmp/ai_nas_s100_grounded_vision_gateway.log 2>&1 &" | Out-Null
  for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Seconds 2
    $visionHealth = Test-HttpJson $visionHealthUrl
    if ($visionHealth -and $visionHealth.ready) { break }
  }
}
if (-not $visionHealth -or -not $visionHealth.ready) {
  throw "S100 grounded vision gateway not ready at $visionHealthUrl"
}

$existing = Get-NetTCPConnection -LocalPort $PortalPort -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($existing -and $RestartPortal) {
  Stop-Process -Id $existing.OwningProcess -Force
  Start-Sleep -Seconds 1
  $existing = $null
}
if ($existing -and $resolvedOfficialManagerUrl) {
  $currentConfig = Test-HttpJson "http://127.0.0.1:${PortalPort}/api/portal/config"
  if ($currentConfig -and $currentConfig.official_manager_url -and $currentConfig.official_manager_url -ne $resolvedOfficialManagerUrl) {
    Stop-Process -Id $existing.OwningProcess -Force
    Start-Sleep -Seconds 1
    $existing = $null
  }
}

if (-not $existing) {
  $env:AI_NAS_IMAGE_TEXT_EMBEDDING_ENDPOINT = "http://${S100Host}:${ClipPort}/embed"
  $env:AI_NAS_IMAGE_TEXT_EMBEDDING_MODEL = "s100p-clip-vit-base-patch32"
  $env:AI_NAS_OCR_ENDPOINT = "http://${S100Host}:${VisionPort}/ocr"
  $env:AI_NAS_OCR_MODEL = "s100p-ppocrv3-hbm"
  $env:AI_NAS_VISION_DETECTOR_ENDPOINT = "http://${S100Host}:${VisionPort}/region"
  $env:AI_NAS_VISION_DETECTOR_MODEL = "s100p-yolov8n-hbm"
  $env:AI_NAS_REGION_ATTRIBUTE_ENDPOINT = "http://${S100Host}:${VisionPort}/region"
  $env:AI_NAS_REGION_ATTRIBUTE_MODEL = "s100p-yolov8n-hbm-cv-region-v1"
  $env:AI_NAS_VISION_CAPTION_ENDPOINT = "http://${S100Host}:${VisionPort}/chat/completions"
  $env:AI_NAS_VISION_CAPTION_MODEL = "s100p-grounded-caption-yolo-ppocr-v1"
  $env:AI_NAS_OCR_TIMEOUT_SECONDS = "120"
  $env:AI_NAS_REGION_ATTRIBUTE_TIMEOUT_SECONDS = "120"
  $env:AI_NAS_VISION_CAPTION_TIMEOUT_SECONDS = "180"
  $server = Join-Path $Workspace "scripts\probes\ai_nas_operator_portal_server.py"
  $args = @(
    $server,
    "--bind", "127.0.0.1",
    "--port", "$PortalPort",
    "--personal-root", "F:\mnt\nas\openclaw\Personal",
    "--report-root", "F:\mnt\nas\openclaw\reports\ai_nas_mvp",
    "--sqlite-index-path", "F:\mnt\nas\openclaw\reports\ai_nas_mvp\personal_inventory.sqlite3",
    "--identity-db-path", "F:\mnt\nas\openclaw\reports\ai_nas_mvp\portal_runtime_current\identity.sqlite3",
    "--snapshot-db-path", "F:\mnt\nas\openclaw\reports\ai_nas_mvp\portal_runtime_current\snapshot.sqlite3",
    "--backup-db-path", "F:\mnt\nas\openclaw\reports\ai_nas_mvp\portal_runtime_current\backup.sqlite3",
    "--media-db-path", "F:\mnt\nas\openclaw\reports\ai_nas_mvp\portal_runtime_current\media.sqlite3",
    "--ops-db-path", "F:\mnt\nas\openclaw\reports\ai_nas_mvp\portal_runtime_current\ops.sqlite3",
    "--app-db-path", "F:\mnt\nas\openclaw\reports\ai_nas_mvp\portal_runtime_current\apps.sqlite3",
    "--schedule-db-path", "F:\mnt\nas\openclaw\reports\ai_nas_mvp\portal_runtime_current\schedules.sqlite3",
    "--nas-portal"
  )
  if ($resolvedOfficialManagerUrl) {
    $args += @("--official-manager-url", $resolvedOfficialManagerUrl)
  }
  $args += @("--no-refresh")
  $portal = Start-Process -FilePath $Python -ArgumentList $args -WorkingDirectory $Workspace -WindowStyle Hidden -PassThru
} else {
  $portal = Get-Process -Id $existing.OwningProcess
}

for ($i = 0; $i -lt 40; $i++) {
  $health = Test-HttpJson "http://127.0.0.1:${PortalPort}/api/health"
  if ($health -and $health.ok) { break }
  Start-Sleep -Milliseconds 500
}

[pscustomobject]@{
  ok = $true
  portal_url = "http://127.0.0.1:${PortalPort}/"
  portal_pid = $portal.Id
  clip_health_url = $clipHealthUrl
  clip_ready = [bool]$clipHealth.ready
  vision_health_url = $visionHealthUrl
  vision_ready = [bool]$visionHealth.ready
  embedding_endpoint = "http://${S100Host}:${ClipPort}/embed"
  ocr_endpoint = "http://${S100Host}:${VisionPort}/ocr"
  region_endpoint = "http://${S100Host}:${VisionPort}/region"
  caption_endpoint = "http://${S100Host}:${VisionPort}/chat/completions"
  official_manager_url = $resolvedOfficialManagerUrl
  official_tunnel_pid = if ($officialTunnel) { $officialTunnel.Id } else { $null }
} | ConvertTo-Json -Depth 5
