param(
  [Parameter(Mandatory)]
  [ValidateSet('start', 'stop', 'status', 'restart', 'ensure')]
  [string]$Action,

  [int]$IntervalMinutes = 30,
  [int]$RemoteTimeoutSeconds = 45,
  [int]$StaleGraceMinutes = 5,
  [switch]$NoA010Refresh,
  [switch]$AsObject
)

$ErrorActionPreference = 'Stop'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir '..\..')).Path
$OutputDir = Join-Path $RepoRoot 'logs\baseline-audit'
$PidPath = Join-Path $OutputDir 'baseline_audit_loop.pid'
$CommandPath = Join-Path $OutputDir 'baseline_audit_loop.command.txt'
$StartedPath = Join-Path $OutputDir 'baseline_audit_loop.started.json'

function Get-LoopProcess {
  if (-not (Test-Path -LiteralPath $PidPath)) {
    return $null
  }
  $raw = (Get-Content -LiteralPath $PidPath -Raw).Trim()
  if (-not ($raw -match '^[0-9]+$')) {
    return $null
  }
  return Get-Process -Id ([int]$raw) -ErrorAction SilentlyContinue
}

function Stop-Loop {
  $process = Get-LoopProcess
  if ($null -ne $process) {
    Stop-Process -Id $process.Id -Force
    Start-Sleep -Seconds 1
    return "stopped pid=$($process.Id)"
  }
  return 'not_running'
}

function Start-Loop {
  New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
  $existing = Get-LoopProcess
  if ($null -ne $existing) {
    return [pscustomobject]@{
      status = 'already_running'
      pid = $existing.Id
      command = (Get-CimInstance Win32_Process -Filter "ProcessId=$($existing.Id)" | Select-Object -ExpandProperty CommandLine)
    }
  }

  $args = @(
    '-ExecutionPolicy', 'Bypass',
    '-File', '.\scripts\windows\baseline-audit.ps1',
    '-Iterations', '0',
    '-IntervalMinutes', [string]$IntervalMinutes,
    '-RemoteTimeoutSeconds', [string]$RemoteTimeoutSeconds
  )
  if (-not $NoA010Refresh) {
    $args += '-RefreshA010ReadOnly'
  }

  $process = Start-Process -FilePath 'powershell.exe' `
    -ArgumentList $args `
    -WorkingDirectory $RepoRoot `
    -WindowStyle Hidden `
    -PassThru

  $process.Id | Set-Content -LiteralPath $PidPath -Encoding ASCII
  ('powershell.exe ' + ($args -join ' ')) | Set-Content -LiteralPath $CommandPath -Encoding UTF8
  [pscustomobject]@{
    startedAt = (Get-Date).ToString('o')
    pid = $process.Id
    intervalMinutes = $IntervalMinutes
    remoteTimeoutSeconds = $RemoteTimeoutSeconds
    refreshA010ReadOnly = (-not $NoA010Refresh)
    command = ('powershell.exe ' + ($args -join ' '))
  } | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $StartedPath -Encoding UTF8

  Start-Sleep -Seconds 2
  return [pscustomobject]@{
    status = 'started'
    pid = $process.Id
    command = ('powershell.exe ' + ($args -join ' '))
  }
}

function Get-StartedMetadata {
  if (-not (Test-Path -LiteralPath $StartedPath)) {
    return $null
  }
  try {
    return Get-Content -Raw -Encoding UTF8 -LiteralPath $StartedPath | ConvertFrom-Json
  } catch {
    return [pscustomobject]@{
      parseError = $_.Exception.Message
    }
  }
}

function Get-Status {
  $process = Get-LoopProcess
  $startedMetadata = Get-StartedMetadata
  $latest = Get-ChildItem -LiteralPath $OutputDir -Filter 'baseline_audit_*.md' -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
  $latestJson = $null
  $latestPayload = $null
  if ($latest) {
    $latestJson = [IO.Path]::ChangeExtension($latest.FullName, '.json')
    if (Test-Path -LiteralPath $latestJson) {
      try {
        $latestPayload = Get-Content -Raw -Encoding UTF8 -LiteralPath $latestJson | ConvertFrom-Json
      } catch {
        $latestPayload = [pscustomobject]@{
          parseError = $_.Exception.Message
        }
      }
    }
  }

  $configuredIntervalMinutes = $IntervalMinutes
  if ($startedMetadata -and ($startedMetadata.PSObject.Properties.Name -contains 'intervalMinutes')) {
    $configuredIntervalMinutes = [int]$startedMetadata.intervalMinutes
  }
  $staleAfterMinutes = $configuredIntervalMinutes + $StaleGraceMinutes
  $latestReportAgeMinutes = $null
  $latestReportFresh = $false
  $freshReason = 'no_report'
  if ($latest) {
    $latestReportAgeMinutes = [math]::Round(((Get-Date) - $latest.LastWriteTime).TotalMinutes, 2)
    $latestReportFresh = ($latestReportAgeMinutes -le $staleAfterMinutes)
    $freshReason = if ($latestReportFresh) { 'fresh' } else { 'stale' }
  }
  $loopHealthy = (($null -ne $process) -and $latestReportFresh)

  [pscustomobject]@{
    running = ($null -ne $process)
    pid = if ($process) { $process.Id } else { $null }
    processName = if ($process) { $process.ProcessName } else { $null }
    startTime = if ($process) { $process.StartTime.ToString('o') } else { $null }
    command = if ($process) { (Get-CimInstance Win32_Process -Filter "ProcessId=$($process.Id)" | Select-Object -ExpandProperty CommandLine) } else { $null }
    pidPath = $PidPath
    commandPath = $CommandPath
    startedMetadata = $startedMetadata
    configuredIntervalMinutes = $configuredIntervalMinutes
    staleGraceMinutes = $StaleGraceMinutes
    staleAfterMinutes = $staleAfterMinutes
    latestReportAgeMinutes = $latestReportAgeMinutes
    latestReportFresh = $latestReportFresh
    latestReportFreshReason = $freshReason
    loopHealthy = $loopHealthy
    latestReport = if ($latest) { $latest.FullName } else { $null }
    latestJson = if ($latestJson) { $latestJson } else { $null }
    latestReportTime = if ($latest) { $latest.LastWriteTime.ToString('o') } else { $null }
    latestDecision = if ($latestPayload -and ($latestPayload.PSObject.Properties.Name -contains 'decision')) { $latestPayload.decision } else { $null }
    latestChecks = if ($latestPayload -and ($latestPayload.PSObject.Properties.Name -contains 'checks')) { $latestPayload.checks } else { $null }
    latestA010Checkpoint = if ($latestPayload -and ($latestPayload.PSObject.Properties.Name -contains 'a010Checkpoint')) { $latestPayload.a010Checkpoint } else { $null }
    latestFindings = if ($latestPayload -and ($latestPayload.PSObject.Properties.Name -contains 'findings')) { $latestPayload.findings } else { $null }
  }
}

function Ensure-Loop {
  $before = Get-Status
  if ($before.loopHealthy) {
    return [pscustomobject]@{
      status = 'healthy'
      action = 'none'
      before = $before
      after = $before
    }
  }

  $stopStatus = Stop-Loop
  $startStatus = Start-Loop
  $after = Get-Status
  return [pscustomobject]@{
    status = if ($after.loopHealthy) { 'repaired' } else { 'started_waiting_for_first_report' }
    action = 'restart'
    stopped = $stopStatus
    started = $startStatus
    before = $before
    after = $after
  }
}

$result = $null
switch ($Action) {
  'start' {
    $result = Start-Loop
  }
  'stop' {
    $result = [pscustomobject]@{ status = (Stop-Loop) }
  }
  'restart' {
    $stopStatus = Stop-Loop
    $startStatus = Start-Loop
    $result = [pscustomobject]@{
      stopped = $stopStatus
      started = $startStatus
    }
  }
  'status' {
    $result = Get-Status
  }
  'ensure' {
    $result = Ensure-Loop
  }
}

if ($AsObject) {
  $result
} else {
  $result | ConvertTo-Json -Depth 5
}
