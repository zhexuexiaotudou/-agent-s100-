param(
  [Parameter(Mandatory)]
  [ValidateSet('start', 'stop', 'status', 'restart', 'ensure', 'run')]
  [string]$Action,

  [int]$CheckIntervalMinutes = 5,
  [int]$LoopIntervalMinutes = 30,
  [int]$RemoteTimeoutSeconds = 45,
  [int]$StaleGraceMinutes = 5,
  [switch]$NoA010Refresh,
  [switch]$AsObject
)

$ErrorActionPreference = 'Stop'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir '..\..')).Path
$OutputDir = Join-Path $RepoRoot 'logs\baseline-audit'
$LoopScript = Join-Path $ScriptDir 'baseline-audit-loop.ps1'
$PidPath = Join-Path $OutputDir 'baseline_audit_watchdog.pid'
$CommandPath = Join-Path $OutputDir 'baseline_audit_watchdog.command.txt'
$StartedPath = Join-Path $OutputDir 'baseline_audit_watchdog.started.json'
$HeartbeatPath = Join-Path $OutputDir 'baseline_audit_watchdog.heartbeat.jsonl'

function Get-WatchdogProcess {
  if (-not (Test-Path -LiteralPath $PidPath)) {
    return $null
  }
  $raw = (Get-Content -LiteralPath $PidPath -Raw).Trim()
  if (-not ($raw -match '^[0-9]+$')) {
    return $null
  }
  return Get-Process -Id ([int]$raw) -ErrorAction SilentlyContinue
}

function Stop-Watchdog {
  $process = Get-WatchdogProcess
  if ($null -ne $process) {
    Stop-Process -Id $process.Id -Force
    Start-Sleep -Seconds 1
    return "stopped pid=$($process.Id)"
  }
  return 'not_running'
}

function Invoke-LoopEnsure {
  $ensureParams = @{
    Action = 'ensure'
    IntervalMinutes = $LoopIntervalMinutes
    RemoteTimeoutSeconds = $RemoteTimeoutSeconds
    StaleGraceMinutes = $StaleGraceMinutes
    AsObject = $true
  }
  if ($NoA010Refresh) {
    $ensureParams.NoA010Refresh = $true
  }
  return & $LoopScript @ensureParams
}

function Write-Heartbeat {
  param(
    [Parameter(Mandatory)]
    [object]$EnsureResult
  )
  New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
  [pscustomobject]@{
    time = (Get-Date).ToString('o')
    watchdogPid = $PID
    ensureStatus = $EnsureResult.status
    ensureAction = $EnsureResult.action
    loopPid = if ($EnsureResult.after) { $EnsureResult.after.pid } else { $null }
    loopHealthy = if ($EnsureResult.after) { $EnsureResult.after.loopHealthy } else { $null }
    latestDecision = if ($EnsureResult.after) { $EnsureResult.after.latestDecision } else { $null }
    latestReport = if ($EnsureResult.after) { $EnsureResult.after.latestReport } else { $null }
  } | ConvertTo-Json -Compress -Depth 8 | Add-Content -LiteralPath $HeartbeatPath -Encoding UTF8
}

function Start-Watchdog {
  New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
  $existing = Get-WatchdogProcess
  if ($null -ne $existing) {
    return [pscustomobject]@{
      status = 'already_running'
      pid = $existing.Id
      command = (Get-CimInstance Win32_Process -Filter "ProcessId=$($existing.Id)" | Select-Object -ExpandProperty CommandLine)
    }
  }

  $processArgs = @(
    '-ExecutionPolicy', 'Bypass',
    '-File', '.\scripts\windows\baseline-audit-watchdog.ps1',
    '-Action', 'run',
    '-CheckIntervalMinutes', [string]$CheckIntervalMinutes,
    '-LoopIntervalMinutes', [string]$LoopIntervalMinutes,
    '-RemoteTimeoutSeconds', [string]$RemoteTimeoutSeconds,
    '-StaleGraceMinutes', [string]$StaleGraceMinutes
  )
  if ($NoA010Refresh) {
    $processArgs += '-NoA010Refresh'
  }

  $process = Start-Process -FilePath 'powershell.exe' `
    -ArgumentList $processArgs `
    -WorkingDirectory $RepoRoot `
    -WindowStyle Hidden `
    -PassThru

  $process.Id | Set-Content -LiteralPath $PidPath -Encoding ASCII
  ('powershell.exe ' + ($processArgs -join ' ')) | Set-Content -LiteralPath $CommandPath -Encoding UTF8
  [pscustomobject]@{
    startedAt = (Get-Date).ToString('o')
    pid = $process.Id
    checkIntervalMinutes = $CheckIntervalMinutes
    loopIntervalMinutes = $LoopIntervalMinutes
    remoteTimeoutSeconds = $RemoteTimeoutSeconds
    staleGraceMinutes = $StaleGraceMinutes
    refreshA010ReadOnly = (-not $NoA010Refresh)
    command = ('powershell.exe ' + ($processArgs -join ' '))
  } | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $StartedPath -Encoding UTF8

  Start-Sleep -Seconds 3
  return [pscustomobject]@{
    status = 'started'
    pid = $process.Id
    command = ('powershell.exe ' + ($processArgs -join ' '))
  }
}

function Get-LastHeartbeat {
  if (-not (Test-Path -LiteralPath $HeartbeatPath)) {
    return $null
  }
  $line = Get-Content -LiteralPath $HeartbeatPath -Tail 1 -Encoding UTF8
  if (-not $line) {
    return $null
  }
  try {
    return $line | ConvertFrom-Json
  } catch {
    return [pscustomobject]@{
      parseError = $_.Exception.Message
      raw = $line
    }
  }
}

function Get-WatchdogStatus {
  $process = Get-WatchdogProcess
  $lastHeartbeat = Get-LastHeartbeat
  $heartbeatAgeMinutes = $null
  $heartbeatFresh = $false
  $heartbeatClean = $false
  if ($lastHeartbeat -and ($lastHeartbeat.PSObject.Properties.Name -contains 'time')) {
    $heartbeatTime = [datetimeoffset]::Parse([string]$lastHeartbeat.time)
    $heartbeatAgeMinutes = [math]::Round(((Get-Date) - $heartbeatTime.LocalDateTime).TotalMinutes, 2)
    $heartbeatFresh = ($heartbeatAgeMinutes -le ($CheckIntervalMinutes + 2))
    $heartbeatClean = -not ($lastHeartbeat.PSObject.Properties.Name -contains 'error')
  }
  $loopStatus = & $LoopScript -Action status `
    -IntervalMinutes $LoopIntervalMinutes `
    -RemoteTimeoutSeconds $RemoteTimeoutSeconds `
    -StaleGraceMinutes $StaleGraceMinutes `
    -AsObject

  return [pscustomobject]@{
    running = ($null -ne $process)
    pid = if ($process) { $process.Id } else { $null }
    processName = if ($process) { $process.ProcessName } else { $null }
    startTime = if ($process) { $process.StartTime.ToString('o') } else { $null }
    command = if ($process) { (Get-CimInstance Win32_Process -Filter "ProcessId=$($process.Id)" | Select-Object -ExpandProperty CommandLine) } else { $null }
    pidPath = $PidPath
    commandPath = $CommandPath
    startedPath = $StartedPath
    heartbeatPath = $HeartbeatPath
    checkIntervalMinutes = $CheckIntervalMinutes
    heartbeatAgeMinutes = $heartbeatAgeMinutes
    heartbeatFresh = $heartbeatFresh
    heartbeatClean = $heartbeatClean
    lastHeartbeat = $lastHeartbeat
    watchdogHealthy = (($null -ne $process) -and $heartbeatFresh -and $heartbeatClean)
    loopStatus = $loopStatus
  }
}

function Ensure-Watchdog {
  $before = Get-WatchdogStatus
  if ($before.watchdogHealthy -and $before.loopStatus.loopHealthy) {
    return [pscustomobject]@{
      status = 'healthy'
      action = 'none'
      before = $before
      after = $before
    }
  }

  $stopStatus = Stop-Watchdog
  $startStatus = Start-Watchdog
  $after = Get-WatchdogStatus
  return [pscustomobject]@{
    status = if ($after.watchdogHealthy) { 'repaired' } else { 'started_waiting_for_heartbeat' }
    action = 'restart'
    stopped = $stopStatus
    started = $startStatus
    before = $before
    after = $after
  }
}

function Run-Watchdog {
  while ($true) {
    try {
      $ensure = Invoke-LoopEnsure
      Write-Heartbeat -EnsureResult $ensure
    } catch {
      New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
      [pscustomobject]@{
        time = (Get-Date).ToString('o')
        watchdogPid = $PID
        error = $_.Exception.Message
      } | ConvertTo-Json -Compress -Depth 4 | Add-Content -LiteralPath $HeartbeatPath -Encoding UTF8
    }
    Start-Sleep -Seconds ([Math]::Max(1, $CheckIntervalMinutes * 60))
  }
}

$result = $null
switch ($Action) {
  'start' {
    $result = Start-Watchdog
  }
  'stop' {
    $result = [pscustomobject]@{ status = (Stop-Watchdog) }
  }
  'restart' {
    $stopStatus = Stop-Watchdog
    $startStatus = Start-Watchdog
    $result = [pscustomobject]@{
      stopped = $stopStatus
      started = $startStatus
    }
  }
  'status' {
    $result = Get-WatchdogStatus
  }
  'ensure' {
    $result = Ensure-Watchdog
  }
  'run' {
    Run-Watchdog
  }
}

if ($Action -ne 'run') {
  if ($AsObject) {
    $result
  } else {
    $result | ConvertTo-Json -Depth 8
  }
}
