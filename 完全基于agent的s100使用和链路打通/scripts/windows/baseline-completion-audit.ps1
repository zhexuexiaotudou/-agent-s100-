param(
  [switch]$AsObject,
  [switch]$IgnoreSafeProgressTaskHealth,
  [switch]$FailIfIncomplete
)

$ErrorActionPreference = 'Stop'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir '..\..')).Path
$OutputDir = Join-Path $RepoRoot 'logs\baseline-audit'
$SupervisionScript = Join-Path $ScriptDir 'baseline-audit-supervision.ps1'
$S100PTaskScript = Join-Path $ScriptDir 's100p-task.ps1'

function Invoke-PowerShellFile {
  param(
    [Parameter(Mandatory)]
    [string]$Path,
    [string[]]$Arguments = @(),
    [int]$Timeout = 120
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

function Read-RemoteJson {
  param(
    [Parameter(Mandatory)]
    [string]$RemotePath,
    [int]$MaxLines = 1000
  )
  $result = Invoke-PowerShellFile -Path $S100PTaskScript -Arguments @(
    '-Action', 'read-remote-report-file',
    '-RemotePath', $RemotePath,
    '-MaxLines', [string]$MaxLines,
    '-TimeoutSeconds', '90'
  ) -Timeout 120
  if ($result.exitCode -ne 0) {
    throw "Failed to read remote JSON $RemotePath`: $($result.error)"
  }
  return $result.output | ConvertFrom-Json
}

function Get-LatestSafeProgress {
  $latest = Get-ChildItem -LiteralPath $OutputDir -Filter 'baseline_safe_progress_*.json' -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
  if (-not $latest) {
    throw "No safe-progress JSON report found under $OutputDir"
  }
  $payload = Get-Content -Raw -Encoding UTF8 -LiteralPath $latest.FullName | ConvertFrom-Json
  return [pscustomobject]@{
    file = $latest.FullName
    payload = $payload
  }
}

function New-CompletionReport {
  param(
    [Parameter(Mandatory)]
    [object]$Payload
  )
  New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
  $timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
  $jsonPath = Join-Path $OutputDir "baseline_completion_audit_$timestamp.json"
  $mdPath = Join-Path $OutputDir "baseline_completion_audit_$timestamp.md"
  $Payload | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $jsonPath -Encoding UTF8

  $lines = @(
    '# Baseline Completion Audit',
    '',
    "- generated_at: $($Payload.generatedAt)",
    "- completionProven: $($Payload.completionProven)",
    "- supervisionHealthy: $($Payload.supervisionHealthy)",
    "- baselineLane: $($Payload.baselineLane)",
    "- acceptanceOverall: $($Payload.acceptanceOverall)",
    "- passCount: $($Payload.statusCounts.pass)",
    "- notReadyCount: $($Payload.notReadyCount)",
    "- latestAcceptance: $($Payload.latestAcceptance)",
    "- latestSafeProgress: $($Payload.latestSafeProgress)",
    '',
    '## Not Ready Items',
    ''
  )
  foreach ($item in $Payload.notReadyItems) {
    $lines += "- $($item.id) [$($item.status)]: $($item.nextAction)"
  }
  $lines += ''
  $lines += '## Proven Items'
  $lines += ''
  foreach ($item in $Payload.provenItems) {
    $lines += "- $($item.id): $($item.title)"
  }
  $lines | Set-Content -LiteralPath $mdPath -Encoding UTF8

  return [pscustomobject]@{
    markdown = $mdPath
    json = $jsonPath
  }
}

$supervisionArgs = @('-FailOnUnhealthy')
if ($IgnoreSafeProgressTaskHealth) {
  $supervisionArgs += '-IgnoreSafeProgressTaskHealth'
}
$supervisionResult = Invoke-PowerShellFile -Path $SupervisionScript -Arguments $supervisionArgs -Timeout 120
if ($supervisionResult.exitCode -ne 0) {
  throw "Supervision gate failed: $($supervisionResult.error)"
}
$supervision = $supervisionResult.output | ConvertFrom-Json

$safeProgress = Get-LatestSafeProgress
$safePayload = $safeProgress.payload
$acceptancePath = $safePayload.latestBaselineAcceptance
if (-not $acceptancePath) {
  throw "Latest safe-progress report does not include latestBaselineAcceptance: $($safeProgress.file)"
}
$acceptanceJsonPath = $acceptancePath -replace '\.md$', '.json'
$acceptance = Read-RemoteJson -RemotePath $acceptanceJsonPath -MaxLines 1000

$items = @($acceptance.items)
$provenItems = @($items | Where-Object { $_.status -eq 'pass' } | ForEach-Object {
  [pscustomobject]@{
    id = $_.id
    title = $_.title
    status = $_.status
    evidence = $_.evidence
  }
})
$notReadyItems = @($items | Where-Object { $_.status -ne 'pass' } | ForEach-Object {
  [pscustomobject]@{
    id = $_.id
    title = $_.title
    status = $_.status
    evidence = $_.evidence
    nextAction = $_.next_action
  }
})

$completionProven = (
  [bool]$supervision.supervisionHealthy -and
  $acceptance.overall -eq 'ready' -and
  $notReadyItems.Count -eq 0
)

$payload = [pscustomobject]@{
  generatedAt = (Get-Date).ToString('o')
  completionProven = $completionProven
  supervisionHealthy = [bool]$supervision.supervisionHealthy
  baselineLane = $supervision.baselineLane
  acceptanceOverall = $acceptance.overall
  statusCounts = $acceptance.status_counts
  itemCount = $items.Count
  provenCount = $provenItems.Count
  notReadyCount = $notReadyItems.Count
  latestSafeProgress = $safeProgress.file
  latestAcceptance = $acceptancePath
  latestAcceptanceJson = $acceptanceJsonPath
  latestAuditReport = $supervision.auditLoop.latestReport
  a010SnapshotCount = $supervision.a010Checkpoint.snapshotCount
  a010ContinuousRemainingHours = $supervision.a010Checkpoint.continuousRemainingHours
  a010ContinuousEta = $supervision.a010Checkpoint.continuousEta
  provenItems = $provenItems
  notReadyItems = $notReadyItems
}

$report = New-CompletionReport -Payload $payload
$payload | Add-Member -NotePropertyName reportMarkdown -NotePropertyValue $report.markdown
$payload | Add-Member -NotePropertyName reportJson -NotePropertyValue $report.json
$payload | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $report.json -Encoding UTF8

if ($AsObject) {
  $payload
} else {
  $payload | ConvertTo-Json -Depth 12
}

if ($FailIfIncomplete -and -not $completionProven) {
  exit 3
}
