param(
  [Parameter(Mandatory)]
  [ValidateSet('status', 'refresh')]
  [string]$Action,

  [int]$TimeoutSeconds = 240,
  [switch]$AsObject
)

$ErrorActionPreference = 'Stop'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir '..\..')).Path
$OutputDir = Join-Path $RepoRoot 'logs\baseline-audit'
$SupervisionScript = Join-Path $ScriptDir 'baseline-audit-supervision.ps1'
$S100PTaskScript = Join-Path $ScriptDir 's100p-task.ps1'
$CompletionAuditScript = Join-Path $ScriptDir 'baseline-completion-audit.ps1'
$SafeProgressMutexName = 'Global\DiguaBaselineSafeProgress'

function Invoke-PowerShellFile {
  param(
    [Parameter(Mandatory)]
    [string]$Path,
    [string[]]$Arguments = @(),
    [int]$Timeout = 240
  )

  $psi = [System.Diagnostics.ProcessStartInfo]::new()
  $psi.FileName = 'powershell.exe'
  $psi.Arguments = (@('-ExecutionPolicy', 'Bypass', '-File', $Path) + $Arguments | ForEach-Object { ConvertTo-CommandLineArgument $_ }) -join ' '
  $psi.RedirectStandardOutput = $true
  $psi.RedirectStandardError = $true
  $psi.UseShellExecute = $false
  $psi.CreateNoWindow = $true

  $process = [System.Diagnostics.Process]::new()
  $process.StartInfo = $psi
  [void]$process.Start()
  $stdoutTask = $process.StandardOutput.ReadToEndAsync()
  $stderrTask = $process.StandardError.ReadToEndAsync()

  if (-not $process.WaitForExit($Timeout * 1000)) {
    try { $process.Kill($true) } catch {}
    try { $process.WaitForExit(5000) | Out-Null } catch {}
    return [pscustomobject]@{
      exitCode = 124
      timedOut = $true
      output = if ($stdoutTask.IsCompleted) { $stdoutTask.Result } else { '' }
      error = if ($stderrTask.IsCompleted -and $stderrTask.Result) { "Timed out after $Timeout seconds`n$($stderrTask.Result)" } else { "Timed out after $Timeout seconds" }
    }
  }

  try { $process.WaitForExit() } catch {}
  return [pscustomobject]@{
    exitCode = $process.ExitCode
    timedOut = $false
    output = $stdoutTask.Result
    error = $stderrTask.Result
  }
}

function ConvertTo-CommandLineArgument {
  param([AllowNull()][string]$Argument)
  if ($null -eq $Argument) { return '""' }
  if ($Argument -notmatch '[\s"]') { return $Argument }
  $escaped = $Argument -replace '\\', '\\' -replace '"', '\"'
  return '"' + $escaped + '"'
}

function Get-Supervision {
  $result = Invoke-PowerShellFile -Path $SupervisionScript -Arguments @('-FailOnUnhealthy', '-IgnoreSafeProgressTaskHealth') -Timeout 90
  if ($result.exitCode -ne 0) {
    throw "Supervision gate failed: $($result.error)"
  }
  return $result.output | ConvertFrom-Json
}

function Get-A010Checkpoint {
  $checkpoint = Invoke-PowerShellFile -Path $S100PTaskScript -Arguments @(
    '-Action', 'read-a010-latest-checkpoint-json',
    '-TimeoutSeconds', '60'
  ) -Timeout 90
  if ($checkpoint.exitCode -ne 0) {
    return [pscustomobject]@{
      ok = $false
      error = $checkpoint.error
    }
  }
  $payload = $checkpoint.output | ConvertFrom-Json
  return [pscustomobject]@{
    ok = $true
    payload = $payload
  }
}

function Invoke-CompletionAudit {
  if (-not (Test-Path -LiteralPath $CompletionAuditScript)) {
    return [pscustomobject]@{
      ok = $false
      error = "Completion audit script not found: $CompletionAuditScript"
      payload = $null
    }
  }
  $result = Invoke-PowerShellFile -Path $CompletionAuditScript -Arguments @('-IgnoreSafeProgressTaskHealth') -Timeout 120
  if ($result.exitCode -ne 0) {
    return [pscustomobject]@{
      ok = $false
      error = $result.error
      payload = $null
    }
  }
  return [pscustomobject]@{
    ok = $true
    error = $null
    payload = ($result.output | ConvertFrom-Json)
  }
}

function Select-RefreshAction {
  param(
    [Parameter(Mandatory)]
    [string]$Lane
  )
  switch ($Lane) {
    'continue-non-nas-readonly-only' { return 'refresh-baseline-local-readonly' }
    'continue-nas-backed-baseline' { return 'refresh-baseline-readonly' }
    default { return $null }
  }
}

function Extract-OutputPaths {
  param([string]$Output)
  if (-not $Output) { return @() }
  return @($Output -split "`r?`n" | Where-Object { $_ -match '^/root/\.openclaw/workspace/' })
}

function New-ProgressReport {
  param(
    [Parameter(Mandatory)]
    [object]$Payload
  )
  New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
  $timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
  $jsonPath = Join-Path $OutputDir "baseline_safe_progress_$timestamp.json"
  $mdPath = Join-Path $OutputDir "baseline_safe_progress_$timestamp.md"
  $Payload | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $jsonPath -Encoding UTF8

  $lines = @(
    '# Baseline Safe Progress',
    '',
    "- generated_at: $($Payload.generatedAt)",
    "- action: $($Payload.action)",
    "- supervisionHealthy: $($Payload.supervisionHealthy)",
    "- baselineLane: $($Payload.baselineLane)",
    "- selectedRefreshAction: $($Payload.selectedRefreshAction)",
    "- refreshExitCode: $($Payload.refreshExitCode)",
    "- latestAuditReport: $($Payload.latestAuditReportRelative)",
    "- latestBaselineAcceptance: $($Payload.latestBaselineAcceptance)",
    "- latestBaselineNextActionQueue: $($Payload.latestBaselineNextActionQueue)",
    "- latestBaselineEvidenceManifest: $($Payload.latestBaselineEvidenceManifest)",
    "- latestA010Status: $($Payload.a010CheckpointStatus)",
    "- latestA010SnapshotCount: $($Payload.a010SnapshotCount)",
    "- latestA010ContinuousRemainingHours: $($Payload.a010ContinuousRemainingHours)",
    '',
    '## Output Paths',
    ''
  )
  foreach ($path in $Payload.outputPaths) {
    $lines += "- $path"
  }
  $lines | Set-Content -LiteralPath $mdPath -Encoding UTF8

  return [pscustomobject]@{
    markdown = $mdPath
    json = $jsonPath
  }
}

function Convert-ToRepoRelativePath {
  param([string]$Path)
  if (-not $Path) { return $null }
  if ($Path -match '(baseline_audit_[^\\/]+\.md)$') {
    return "logs/baseline-audit/$($Matches[1])"
  }
  if ($Path -match '((baseline_completion_audit|baseline_safe_progress)_[^\\/]+\.(md|json))$') {
    return "logs/baseline-audit/$($Matches[1])"
  }
  $repoRootText = [string]$RepoRoot
  if ($Path.StartsWith($repoRootText, [StringComparison]::OrdinalIgnoreCase)) {
    return ($Path.Substring($repoRootText.Length).TrimStart('\') -replace '\\', '/')
  }
  return $Path
}

function Select-LatestPath {
  param(
    [string[]]$Paths,
    [string]$Pattern
  )
  return @($Paths | Where-Object { $_ -match $Pattern } | Select-Object -Last 1)[0]
}

function New-SkippedPayload {
  param(
    [Parameter(Mandatory)]
    [object]$Supervision,
    [string]$Reason
  )
  return [pscustomobject]@{
    generatedAt = (Get-Date).ToString('o')
    action = $Action
    skipped = $true
    skipReason = $Reason
    supervisionHealthy = [bool]$Supervision.supervisionHealthy
    baselineLane = $Supervision.baselineLane
    selectedRefreshAction = Select-RefreshAction -Lane $Supervision.baselineLane
    refreshExitCode = 0
    refreshTimedOut = $false
    refreshError = $Reason
    outputPaths = @()
    latestAuditReport = $Supervision.auditLoop.latestReport
    latestAuditReportRelative = Convert-ToRepoRelativePath -Path $Supervision.auditLoop.latestReport
    latestBaselineAcceptance = $null
    latestBaselineNextActionQueue = $null
    latestBaselineEvidenceManifest = $null
    a010CheckpointReadable = $true
    a010CheckpointStatus = $Supervision.a010Checkpoint.checkpointStatus
    a010SnapshotCount = $Supervision.a010Checkpoint.snapshotCount
    a010ContinuousRemainingHours = $Supervision.a010Checkpoint.continuousRemainingHours
    a010ContinuousEta = $Supervision.a010Checkpoint.continuousEta
    before = $Supervision
    after = $Supervision
  }
}

$refreshMutex = $null
$refreshLockAcquired = $false
if ($Action -eq 'refresh') {
  $refreshMutex = [System.Threading.Mutex]::new($false, $SafeProgressMutexName)
  $refreshLockAcquired = $refreshMutex.WaitOne(0)
  if (-not $refreshLockAcquired) {
    $supervision = Get-Supervision
    $payload = New-SkippedPayload -Supervision $supervision -Reason 'another safe-progress refresh is already running'
    $report = New-ProgressReport -Payload $payload
    $payload | Add-Member -NotePropertyName reportMarkdown -NotePropertyValue $report.markdown
    $payload | Add-Member -NotePropertyName reportJson -NotePropertyValue $report.json
    $payload | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $report.json -Encoding UTF8
    if ($AsObject) {
      $payload
    } else {
      $payload | ConvertTo-Json -Depth 12
    }
    exit 0
  }
}

$before = Get-Supervision
$selectedRefreshAction = Select-RefreshAction -Lane $before.baselineLane
$refreshResult = $null
$outputPaths = @()

if ($Action -eq 'refresh' -and $selectedRefreshAction) {
  $refreshResult = Invoke-PowerShellFile -Path $S100PTaskScript -Arguments @(
    '-Action', $selectedRefreshAction,
    '-TimeoutSeconds', [string]$TimeoutSeconds
  ) -Timeout ($TimeoutSeconds + 60)
  $outputPaths = Extract-OutputPaths -Output $refreshResult.output
} elseif ($Action -eq 'refresh') {
  $refreshResult = [pscustomobject]@{
    exitCode = 0
    timedOut = $false
    output = ''
    error = "No safe refresh action for lane: $($before.baselineLane)"
  }
}

$after = Get-Supervision
$a010 = Get-A010Checkpoint
$a010Payload = if ($a010.ok) { $a010.payload } else { $null }

$payload = [pscustomobject]@{
  generatedAt = (Get-Date).ToString('o')
  action = $Action
  supervisionHealthy = [bool]$after.supervisionHealthy
  baselineLane = $after.baselineLane
  selectedRefreshAction = $selectedRefreshAction
  refreshExitCode = if ($refreshResult) { $refreshResult.exitCode } else { $null }
  refreshTimedOut = if ($refreshResult) { $refreshResult.timedOut } else { $null }
  refreshError = if ($refreshResult) { $refreshResult.error } else { $null }
  outputPaths = $outputPaths
  latestAuditReport = $after.auditLoop.latestReport
  latestAuditReportRelative = Convert-ToRepoRelativePath -Path $after.auditLoop.latestReport
  latestBaselineAcceptance = Select-LatestPath -Paths $outputPaths -Pattern '/baseline_acceptance_[0-9]{8}-[0-9]{6}\.md$'
  latestBaselineNextActionQueue = Select-LatestPath -Paths $outputPaths -Pattern '/baseline_next_action_queue_[0-9]{8}-[0-9]{6}\.md$'
  latestBaselineEvidenceManifest = Select-LatestPath -Paths $outputPaths -Pattern '/baseline_evidence_manifest_[0-9]{8}-[0-9]{6}\.md$'
  a010CheckpointReadable = [bool]$a010.ok
  a010CheckpointStatus = if ($a010Payload) { $a010Payload.checkpoint_status } else { $null }
  a010SnapshotCount = if ($a010Payload) { $a010Payload.snapshot_count } else { $null }
  a010ContinuousRemainingHours = if ($a010Payload) { $a010Payload.continuous_remaining_hours } else { $null }
  a010ContinuousEta = if ($a010Payload) { $a010Payload.continuous_eta } else { $null }
  before = $before
  after = $after
}

$report = New-ProgressReport -Payload $payload
$payload | Add-Member -NotePropertyName reportMarkdown -NotePropertyValue $report.markdown
$payload | Add-Member -NotePropertyName reportJson -NotePropertyValue $report.json
$payload | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $report.json -Encoding UTF8

if ($Action -eq 'refresh' -and $refreshResult -and $refreshResult.exitCode -eq 0) {
  $completion = Invoke-CompletionAudit
  $completionPayload = $completion.payload
  $payload | Add-Member -NotePropertyName completionAuditOk -NotePropertyValue ([bool]$completion.ok)
  $payload | Add-Member -NotePropertyName completionProven -NotePropertyValue $(if ($completionPayload) { [bool]$completionPayload.completionProven } else { $false })
  $payload | Add-Member -NotePropertyName completionNotReadyCount -NotePropertyValue $(if ($completionPayload) { $completionPayload.notReadyCount } else { $null })
  $payload | Add-Member -NotePropertyName completionAuditReportMarkdown -NotePropertyValue $(if ($completionPayload) { Convert-ToRepoRelativePath -Path $completionPayload.reportMarkdown } else { $null })
  $payload | Add-Member -NotePropertyName completionAuditReportJson -NotePropertyValue $(if ($completionPayload) { Convert-ToRepoRelativePath -Path $completionPayload.reportJson } else { $null })
  $payload | Add-Member -NotePropertyName completionAuditError -NotePropertyValue $completion.error
  $payload | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $report.json -Encoding UTF8
  @(
    '',
    '## Completion Audit',
    '',
    "- completionAuditOk: $($payload.completionAuditOk)",
    "- completionProven: $($payload.completionProven)",
    "- completionNotReadyCount: $($payload.completionNotReadyCount)",
    "- completionAuditReport: $($payload.completionAuditReportMarkdown)"
  ) | Add-Content -LiteralPath $report.markdown -Encoding UTF8
}

if ($AsObject) {
  $payload
} else {
  $payload | ConvertTo-Json -Depth 12
}

if ($Action -eq 'refresh' -and $refreshResult -and $refreshResult.exitCode -ne 0) {
  exit $refreshResult.exitCode
}

if ($refreshLockAcquired -and $refreshMutex) {
  $refreshMutex.ReleaseMutex()
  $refreshMutex.Dispose()
}
