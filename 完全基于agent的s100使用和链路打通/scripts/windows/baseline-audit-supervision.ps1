param(
  [string]$TaskName = 'Digua-Baseline-Audit-Watchdog',
  [string]$SafeProgressTaskName = 'Digua-Baseline-Safe-Progress',
  [switch]$RequireBackgroundAutomation,
  [switch]$IgnoreSafeProgressTaskHealth,
  [switch]$FailOnUnhealthy,
  [switch]$AsObject
)

$ErrorActionPreference = 'Stop'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$TaskScript = Join-Path $ScriptDir 'baseline-audit-watchdog-task.ps1'
$SafeProgressTaskScript = Join-Path $ScriptDir 'baseline-safe-progress-task.ps1'
$WatchdogScript = Join-Path $ScriptDir 'baseline-audit-watchdog.ps1'

function Convert-JsonOutput {
  param(
    [Parameter(Mandatory)]
    [object]$Output
  )
  return ($Output | Out-String) | ConvertFrom-Json
}

function Test-Property {
  param(
    [object]$Object,
    [string]$Name
  )
  return ($null -ne $Object -and ($Object.PSObject.Properties.Name -contains $Name))
}

$task = Convert-JsonOutput (& $TaskScript -Action status -TaskName $TaskName)
$safeProgressTask = Convert-JsonOutput (& $SafeProgressTaskScript -Action status -TaskName $SafeProgressTaskName)
$watchdog = & $WatchdogScript -Action status -AsObject
$loop = $watchdog.loopStatus
$checks = $loop.latestChecks
$a010 = $loop.latestA010Checkpoint

$checkNames = @(
  'powershellSyntaxOk',
  'jsonSyntaxOk',
  'allowlistConsistencyOk',
  'sshOk',
  'openclawOk',
  'remoteScriptValidationOk'
)

$requiredChecksOk = $true
foreach ($name in $checkNames) {
  if (-not (Test-Property $checks $name) -or -not [bool]$checks.$name) {
    $requiredChecksOk = $false
  }
}

if ($RequireBackgroundAutomation) {
  $startupTaskHealthy = (
    [bool]$task.installed -and
    $task.lastTaskResult -eq 0 -and
    $task.triggers -and
    ($task.triggers | Where-Object { $_.triggerType -eq 'MSFT_TaskLogonTrigger' -and $_.enabled })
  )
  $safeProgressTaskHealthy = (
    [bool]$safeProgressTask.installed -and
    $safeProgressTask.lastTaskResult -eq 0 -and
    $safeProgressTask.triggers -and
    ($safeProgressTask.triggers | Where-Object {
      $_.triggerType -eq 'MSFT_TaskTimeTrigger' -and
      $_.enabled -and
      $_.repetitionInterval -eq 'PT30M'
    })
  )
  $watchdogHealthy = [bool]$watchdog.watchdogHealthy
  $loopHealthy = [bool]$loop.loopHealthy
} else {
  $startupTaskHealthy = -not [bool]$task.installed
  $safeProgressTaskHealthy = -not [bool]$safeProgressTask.installed
  $watchdogHealthy = -not [bool]$watchdog.running
  $loopHealthy = -not [bool]$loop.running
}
$latestReportFresh = [bool]$loop.latestReportFresh
$a010Readable = ($null -ne $a010 -and [bool]$a010.ok)
$supervisionHealthy = (
  $startupTaskHealthy -and
  ($IgnoreSafeProgressTaskHealth -or $safeProgressTaskHealthy) -and
  $watchdogHealthy -and
  $loopHealthy -and
  ($latestReportFresh -or -not $RequireBackgroundAutomation) -and
  $requiredChecksOk -and
  $a010Readable
)

$result = [pscustomobject]@{
  generatedAt = (Get-Date).ToString('o')
  mode = if ($RequireBackgroundAutomation) { 'background-automation' } else { 'codex-session-only' }
  backgroundAutomationRequired = [bool]$RequireBackgroundAutomation
  supervisionHealthy = $supervisionHealthy
  baselineLane = $loop.latestDecision
  startupTaskHealthy = $startupTaskHealthy
  safeProgressTaskHealthy = $safeProgressTaskHealthy
  safeProgressTaskHealthIgnored = [bool]$IgnoreSafeProgressTaskHealth
  watchdogHealthy = $watchdogHealthy
  loopHealthy = $loopHealthy
  latestReportFresh = $latestReportFresh
  requiredChecksOk = $requiredChecksOk
  a010Readable = $a010Readable
  task = [pscustomobject]@{
    installed = $task.installed
    taskName = $task.taskName
    state = $task.state
    lastRunTime = $task.lastRunTime
    lastTaskResult = $task.lastTaskResult
    triggerTypes = @($task.triggers | ForEach-Object { $_.triggerType })
  }
  safeProgressTask = [pscustomobject]@{
    installed = $safeProgressTask.installed
    taskName = $safeProgressTask.taskName
    state = $safeProgressTask.state
    lastRunTime = $safeProgressTask.lastRunTime
    lastTaskResult = $safeProgressTask.lastTaskResult
    nextRunTime = $safeProgressTask.nextRunTime
    triggerTypes = @($safeProgressTask.triggers | ForEach-Object { $_.triggerType })
    repetitionIntervals = @($safeProgressTask.triggers | ForEach-Object { $_.repetitionInterval })
  }
  watchdog = [pscustomobject]@{
    pid = $watchdog.pid
    heartbeatFresh = $watchdog.heartbeatFresh
    heartbeatClean = $watchdog.heartbeatClean
    heartbeatAgeMinutes = $watchdog.heartbeatAgeMinutes
    lastEnsureStatus = if ($watchdog.lastHeartbeat) { $watchdog.lastHeartbeat.ensureStatus } else { $null }
    lastEnsureAction = if ($watchdog.lastHeartbeat) { $watchdog.lastHeartbeat.ensureAction } else { $null }
  }
  auditLoop = [pscustomobject]@{
    pid = $loop.pid
    latestReport = $loop.latestReport
    latestJson = $loop.latestJson
    latestReportAgeMinutes = $loop.latestReportAgeMinutes
    latestDecision = $loop.latestDecision
  }
  checks = $checks
  a010Checkpoint = $a010
  findings = $loop.latestFindings
}

if ($AsObject) {
  $result
} else {
  $result | ConvertTo-Json -Depth 10
}

if ($FailOnUnhealthy -and -not $supervisionHealthy) {
  exit 2
}
