param(
  [int]$Iterations = 1,
  [int]$IntervalMinutes = 30,
  [string]$OutputDir,
  [int]$RemoteTimeoutSeconds = 60,
  [switch]$RefreshA010ReadOnly,
  [switch]$SkipRemote
)

$ErrorActionPreference = 'Stop'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir '..\..')).Path
if (-not $OutputDir) {
  $OutputDir = Join-Path $RepoRoot 'logs\baseline-audit'
}

function Invoke-AuditStep {
  param(
    [Parameter(Mandatory)][string]$Name,
    [Parameter(Mandatory)][scriptblock]$ScriptBlock,
    [object[]]$ArgumentList = @(),
    [int]$TimeoutSeconds = 30
  )

  $started = Get-Date
  $job = Start-Job -ScriptBlock $ScriptBlock -ArgumentList $ArgumentList
  if (-not (Wait-Job -Job $job -Timeout $TimeoutSeconds)) {
    Stop-Job -Job $job -ErrorAction SilentlyContinue
    Remove-Job -Job $job -Force -ErrorAction SilentlyContinue
    return [pscustomobject]@{
      name = $Name
      exitCode = 124
      timedOut = $true
      startedAt = $started.ToString('o')
      endedAt = (Get-Date).ToString('o')
      output = ''
      error = "Timed out after $TimeoutSeconds seconds"
    }
  }

  $received = Receive-Job -Job $job
  Remove-Job -Job $job -Force -ErrorAction SilentlyContinue
  $payload = $received | Select-Object -Last 1
  if ($null -eq $payload -or -not ($payload.PSObject.Properties.Name -contains 'exitCode')) {
    $payload = [pscustomobject]@{
      exitCode = 1
      output = ($received | Out-String)
      error = 'Audit step did not return a structured payload.'
    }
  }

  return [pscustomobject]@{
    name = $Name
    exitCode = [int]$payload.exitCode
    timedOut = $false
    startedAt = $started.ToString('o')
    endedAt = (Get-Date).ToString('o')
    output = [string]$payload.output
    error = [string]$payload.error
  }
}

function Invoke-RepoCommandStep {
  param(
    [string]$Name,
    [string[]]$Command,
    [int]$TimeoutSeconds = 30
  )

  Invoke-AuditStep -Name $Name -TimeoutSeconds $TimeoutSeconds -ArgumentList @($RepoRoot, $Command) -ScriptBlock {
    param($Root, $CommandParts)
    Set-Location -LiteralPath $Root
    try {
      $exe = $CommandParts[0]
      $args = @($CommandParts | Select-Object -Skip 1)
      $text = (& $exe @args 2>&1 | Out-String)
      $code = if ($null -eq $LASTEXITCODE) { 0 } else { $LASTEXITCODE }
      [pscustomobject]@{ exitCode = $code; output = $text; error = '' }
    } catch {
      [pscustomobject]@{ exitCode = 1; output = ''; error = $_.Exception.Message }
    }
  }
}

function Invoke-S100PTaskStep {
  param(
    [string]$Action,
    [int]$TimeoutSeconds
  )

  Invoke-AuditStep -Name "s100p-$Action" -TimeoutSeconds ($TimeoutSeconds + 15) -ArgumentList @($RepoRoot, $Action, $TimeoutSeconds) -ScriptBlock {
    param($Root, $ActionName, $RemoteTimeout)
    Set-Location -LiteralPath $Root
    try {
      $text = (& powershell.exe -ExecutionPolicy Bypass -File '.\scripts\windows\s100p-task.ps1' -Action $ActionName -TimeoutSeconds $RemoteTimeout 2>&1 | Out-String)
      $code = if ($null -eq $LASTEXITCODE) { 0 } else { $LASTEXITCODE }
      [pscustomobject]@{ exitCode = $code; output = $text; error = '' }
    } catch {
      [pscustomobject]@{ exitCode = 1; output = ''; error = $_.Exception.Message }
    }
  }
}

function Test-PowerShellSyntax {
  param([Parameter(Mandatory)][string]$Path)

  $parseErrors = $null
  [System.Management.Automation.PSParser]::Tokenize(
    (Get-Content -Raw -LiteralPath $Path),
    [ref]$parseErrors
  ) | Out-Null

  [pscustomobject]@{
    path = (Resolve-Path -LiteralPath $Path).Path
    ok = ($null -eq $parseErrors -or $parseErrors.Count -eq 0)
    errors = @($parseErrors | ForEach-Object { $_.Message })
  }
}

function Test-JsonSyntax {
  param([Parameter(Mandatory)][string]$Path)

  try {
    Get-Content -Raw -Encoding UTF8 -LiteralPath $Path | ConvertFrom-Json | Out-Null
    [pscustomobject]@{
      path = (Resolve-Path -LiteralPath $Path).Path
      ok = $true
      errors = @()
    }
  } catch {
    [pscustomobject]@{
      path = (Resolve-Path -LiteralPath $Path).Path
      ok = $false
      errors = @($_.Exception.Message)
    }
  }
}

function Test-AllowlistConsistency {
  param(
    [Parameter(Mandatory)][string]$AllowlistPath,
    [Parameter(Mandatory)][string]$RunnerPath
  )

  $errors = [System.Collections.Generic.List[string]]::new()
  try {
    $allowlist = Get-Content -Raw -Encoding UTF8 -LiteralPath $AllowlistPath | ConvertFrom-Json
    $runner = Get-Content -Raw -Encoding UTF8 -LiteralPath $RunnerPath
    $seen = @{}

    foreach ($tool in @($allowlist.tools)) {
      $id = [string]$tool.id
      $script = [string]$tool.script
      if (-not $id) {
        $errors.Add('Tool entry is missing id.') | Out-Null
        continue
      }
      if ($seen.ContainsKey($id)) {
        $errors.Add(("Duplicate tool id: {0}" -f $id)) | Out-Null
      }
      $seen[$id] = $true

      if ($id -notmatch '^[a-z0-9_]+$') {
        $errors.Add(("Tool id uses a non-standard format: {0}" -f $id)) | Out-Null
      }
      if (-not $script) {
        $errors.Add(("Tool {0} is missing script path." -f $id)) | Out-Null
      } else {
        $scriptPath = Join-Path $RepoRoot ($script -replace '/', [IO.Path]::DirectorySeparatorChar)
        if (-not (Test-Path -LiteralPath $scriptPath)) {
          $errors.Add(("Tool {0} script does not exist locally: {1}" -f $id, $script)) | Out-Null
        }
        if ($runner -notmatch [regex]::Escape($script)) {
          $errors.Add(("Tool {0} script path is not referenced by run_allowlisted_tool.sh: {1}" -f $id, $script)) | Out-Null
        }
      }

      $casePattern = '(?m)^\s*' + [regex]::Escape($id) + '\)'
      if ($runner -notmatch $casePattern) {
        $errors.Add(("Tool {0} has no case branch in run_allowlisted_tool.sh." -f $id)) | Out-Null
      }

      $mode = [string]$tool.mode
      if (-not $mode) {
        $errors.Add(("Tool {0} is missing mode." -f $id)) | Out-Null
      }
      $hasOutputs = $tool.PSObject.Properties.Name -contains 'approvedOutputPrefixes'
      if (-not $hasOutputs -or @($tool.approvedOutputPrefixes).Count -eq 0) {
        $errors.Add(("Tool {0} is missing approvedOutputPrefixes." -f $id)) | Out-Null
      }
    }
  } catch {
    $errors.Add($_.Exception.Message) | Out-Null
  }

  [pscustomobject]@{
    ok = ($errors.Count -eq 0)
    errors = @($errors)
  }
}

function Add-Finding {
  param(
    [System.Collections.Generic.List[object]]$Findings,
    [string]$Severity,
    [string]$Area,
    [string]$Message
  )
  $Findings.Add([pscustomobject]@{
    severity = $Severity
    area = $Area
    message = $Message
  }) | Out-Null
}

function Test-NasReachableOutput {
  param([string]$Output)

  return ($Output -match 'bytes from 169\.254\.110\.209') -or
    ($Output -match '\b[1-9][0-9]* received\b')
}

function ConvertTo-A010CheckpointSummary {
  param([string]$JsonText)

  if (-not $JsonText) {
    return $null
  }
  try {
    $payload = $JsonText | ConvertFrom-Json
    if ($payload.PSObject.Properties.Name -contains 'error') {
      return [pscustomobject]@{
        ok = $false
        error = [string]$payload.error
      }
    }
    return [pscustomobject]@{
      ok = $true
      report = [string]$payload.report
      checkpointStatus = [string]$payload.checkpoint_status
      snapshotCount = $payload.snapshot_count
      elapsedHours = $payload.elapsed_hours
      remainingHours = $payload.remaining_hours
      maxGapHours = $payload.max_gap_hours
      gapEventCount = $payload.gap_event_count
      continuousStartAt = [string]$payload.continuous_start_at
      continuousElapsedHours = $payload.continuous_elapsed_hours
      continuousRemainingHours = $payload.continuous_remaining_hours
      continuousEta = [string]$payload.continuous_eta
      snapshotsWithGatewayErrors = $payload.snapshots_with_gateway_errors
      snapshotsWithOomErrors = $payload.snapshots_with_oom_errors
    }
  } catch {
    return [pscustomobject]@{
      ok = $false
      error = $_.Exception.Message
    }
  }
}

function New-AuditReport {
  New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
  $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
  $startedAt = Get-Date
  $findings = [System.Collections.Generic.List[object]]::new()
  $commands = [System.Collections.Generic.List[object]]::new()
  $a010Checkpoint = $null

  $commands.Add((Invoke-RepoCommandStep -Name 'git-status' -Command @('git.exe', 'status', '--short', '--branch') -TimeoutSeconds 20)) | Out-Null
  $commands.Add((Invoke-RepoCommandStep -Name 'git-diff-check' -Command @('git.exe', 'diff', '--check') -TimeoutSeconds 20)) | Out-Null

  $syntax = @(
    (Test-PowerShellSyntax -Path (Join-Path $RepoRoot 'scripts\windows\s100p-task.ps1')),
    (Test-PowerShellSyntax -Path (Join-Path $RepoRoot 'scripts\startup_link_check\S100P-NAS-LinkCheck.ps1')),
    (Test-PowerShellSyntax -Path $PSCommandPath)
  )

  $jsonSyntax = @(
    (Test-JsonSyntax -Path (Join-Path $RepoRoot 'scripts\tool_allowlist.json')),
    (Test-JsonSyntax -Path (Join-Path $RepoRoot 'scripts\startup_link_check\link-check.config.json'))
  )
  $allowlistConsistency = Test-AllowlistConsistency `
    -AllowlistPath (Join-Path $RepoRoot 'scripts\tool_allowlist.json') `
    -RunnerPath (Join-Path $RepoRoot 'scripts\run_allowlisted_tool.sh')

  foreach ($item in $syntax) {
    if (-not $item.ok) {
      Add-Finding -Findings $findings -Severity 'blocker' -Area 'script-syntax' -Message ("PowerShell parse failed: {0}" -f $item.path)
    }
  }
  foreach ($item in $jsonSyntax) {
    if (-not $item.ok) {
      Add-Finding -Findings $findings -Severity 'blocker' -Area 'json-syntax' -Message ("JSON parse failed: {0}: {1}" -f $item.path, ($item.errors -join '; '))
    }
  }
  if (-not $allowlistConsistency.ok) {
    Add-Finding -Findings $findings -Severity 'blocker' -Area 'tool-allowlist' -Message ("Allowlist consistency failed: {0}" -f ($allowlistConsistency.errors -join '; '))
  }

  if (-not $SkipRemote) {
    $commands.Add((Invoke-S100PTaskStep -Action 'ssh-smoke' -TimeoutSeconds $RemoteTimeoutSeconds)) | Out-Null
    $commands.Add((Invoke-S100PTaskStep -Action 'diagnose-nas' -TimeoutSeconds $RemoteTimeoutSeconds)) | Out-Null
    $commands.Add((Invoke-S100PTaskStep -Action 'diagnose-openclaw' -TimeoutSeconds $RemoteTimeoutSeconds)) | Out-Null
    $commands.Add((Invoke-S100PTaskStep -Action 'validate-baseline-scripts-readonly' -TimeoutSeconds $RemoteTimeoutSeconds)) | Out-Null
  }

  $ssh = $commands | Where-Object { $_.name -eq 's100p-ssh-smoke' } | Select-Object -First 1
  $nas = $commands | Where-Object { $_.name -eq 's100p-diagnose-nas' } | Select-Object -First 1
  $openclaw = $commands | Where-Object { $_.name -eq 's100p-diagnose-openclaw' } | Select-Object -First 1
  $remoteValidation = $commands | Where-Object { $_.name -eq 's100p-validate-baseline-scripts-readonly' } | Select-Object -First 1
  $gitStatus = $commands | Where-Object { $_.name -eq 'git-status' } | Select-Object -First 1
  $diffCheck = $commands | Where-Object { $_.name -eq 'git-diff-check' } | Select-Object -First 1

  if ($diffCheck.exitCode -ne 0) {
    Add-Finding -Findings $findings -Severity 'blocker' -Area 'format' -Message 'git diff --check reported whitespace or patch hygiene errors.'
  }
  if ($gitStatus.output -match '^\?\?' -or $gitStatus.output -match '^[ MADRCU]M' -or $gitStatus.output -match '^M') {
    Add-Finding -Findings $findings -Severity 'info' -Area 'worktree' -Message 'Working tree has changes; keep baseline edits scoped and documented.'
  }

  $sshOk = $SkipRemote -or ($ssh.exitCode -eq 0 -and $ssh.output -match 'S100P_SSH_OK')
  $nasReachable = $false
  $nasMounted = $false
  $openclawOk = $SkipRemote -or ($openclaw.exitCode -eq 0 -and $openclaw.output -match 'Active:\s+active|^active$|openclaw-gateway.service: active')
  $remoteScriptValidationOk = $SkipRemote -or ($remoteValidation.exitCode -eq 0 -and $remoteValidation.output -match 'REMOTE_BASELINE_SCRIPT_VALIDATION_OK')

  if (-not $SkipRemote) {
    if (-not $sshOk) {
      Add-Finding -Findings $findings -Severity 'blocker' -Area 's100p' -Message 'S100P SSH smoke failed; stop remote baseline actions until SSH is restored.'
    }

    if ($nas) {
      $nasReachable = Test-NasReachableOutput -Output $nas.output
      $nasMounted = ($nas.output -match '169\.254\.110\.209:/OpenClawWorkspace') -or ($nas.output -match '\stype nfs')
      if (-not $nasReachable) {
        Add-Finding -Findings $findings -Severity 'blocker' -Area 'nas' -Message 'NAS remains L2/IP unreachable from S100P; credentials cannot repair this path until the NAS responds on the link.'
      } elseif (-not $nasMounted) {
        Add-Finding -Findings $findings -Severity 'warn' -Area 'nas' -Message 'NAS is reachable but the NFS workspace is not confirmed mounted; run the mount runbook before NAS-backed evidence refresh.'
      }
    }

    if (-not $openclawOk) {
      Add-Finding -Findings $findings -Severity 'blocker' -Area 'openclaw' -Message 'OpenClaw gateway is not confirmed active.'
    }
    if (-not $remoteScriptValidationOk) {
      Add-Finding -Findings $findings -Severity 'blocker' -Area 'remote-script-validation' -Message 'S100P baseline script validation failed; fix remote Bash/JSON before refreshing evidence.'
    }

    if (-not $nasReachable) {
      Add-Finding -Findings $findings -Severity 'warn' -Area 'overnight' -Message 'Skipped overnight status because NAS is not reachable; this avoids blocking on NAS-backed autofs paths.'
    } else {
      $commands.Add((Invoke-S100PTaskStep -Action 'check-overnight' -TimeoutSeconds $RemoteTimeoutSeconds)) | Out-Null
    }
  }

  $decision = 'continue'
  if (($findings | Where-Object { $_.severity -eq 'blocker' }).Count -gt 0) {
    $decision = 'hold-blocked-items'
  }
  if ($sshOk -and $openclawOk -and -not $nasReachable) {
    $decision = 'continue-non-nas-readonly-only'
  }
  if ($sshOk -and $openclawOk -and $nasReachable -and $nasMounted) {
    $decision = 'continue-nas-backed-baseline'
  }

  if (-not $SkipRemote -and $RefreshA010ReadOnly -and $decision -in @('continue-non-nas-readonly-only', 'continue-nas-backed-baseline', 'continue')) {
    $a010Refresh = Invoke-S100PTaskStep -Action 'refresh-a010-local-readonly' -TimeoutSeconds ([Math]::Max(180, $RemoteTimeoutSeconds))
    $commands.Add($a010Refresh) | Out-Null
    if ($a010Refresh.exitCode -ne 0) {
      Add-Finding -Findings $findings -Severity 'warn' -Area 'a010-refresh' -Message 'Automatic A-010 read-only refresh failed; keep the audit decision but inspect the refresh command output.'
    }
    $a010Read = Invoke-S100PTaskStep -Action 'read-a010-latest-checkpoint-json' -TimeoutSeconds $RemoteTimeoutSeconds
    $commands.Add($a010Read) | Out-Null
    if ($a010Read.exitCode -eq 0) {
      $a010Checkpoint = ConvertTo-A010CheckpointSummary -JsonText $a010Read.output
      if ($null -eq $a010Checkpoint -or -not $a010Checkpoint.ok) {
        Add-Finding -Findings $findings -Severity 'warn' -Area 'a010-checkpoint' -Message 'Automatic A-010 checkpoint JSON could not be parsed after refresh.'
      }
    } else {
      Add-Finding -Findings $findings -Severity 'warn' -Area 'a010-checkpoint' -Message 'Automatic A-010 checkpoint JSON read failed after refresh.'
    }
  }

  $report = [pscustomobject]@{
    schema = 'digua-baseline-audit-v1'
    startedAt = $startedAt.ToString('o')
    endedAt = (Get-Date).ToString('o')
    repoRoot = $RepoRoot
    intervalMinutes = $IntervalMinutes
    decision = $decision
    checks = [pscustomobject]@{
      powershellSyntaxOk = (($syntax | Where-Object { -not $_.ok }).Count -eq 0)
      jsonSyntaxOk = (($jsonSyntax | Where-Object { -not $_.ok }).Count -eq 0)
      allowlistConsistencyOk = $allowlistConsistency.ok
      sshOk = $sshOk
      nasReachable = $nasReachable
      nasMounted = $nasMounted
      openclawOk = $openclawOk
      remoteScriptValidationOk = $remoteScriptValidationOk
    }
    findings = @($findings)
    a010Checkpoint = $a010Checkpoint
    commands = @($commands)
  }

  $jsonPath = Join-Path $OutputDir "baseline_audit_$stamp.json"
  $mdPath = Join-Path $OutputDir "baseline_audit_$stamp.md"
  $report | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $jsonPath -Encoding UTF8

  $lines = [System.Collections.Generic.List[string]]::new()
  $lines.Add('# Baseline Audit') | Out-Null
  $lines.Add('') | Out-Null
  $lines.Add(("Time: {0}" -f $report.endedAt)) | Out-Null
  $lines.Add(('Decision: `{0}`' -f $report.decision)) | Out-Null
  $lines.Add('') | Out-Null
  $lines.Add('## Checks') | Out-Null
  foreach ($name in @('powershellSyntaxOk', 'jsonSyntaxOk', 'allowlistConsistencyOk', 'sshOk', 'nasReachable', 'nasMounted', 'openclawOk', 'remoteScriptValidationOk')) {
    $value = $report.checks | Select-Object -ExpandProperty $name
    $lines.Add(('- {0}: `{1}`' -f $name, $value)) | Out-Null
  }
  $lines.Add('') | Out-Null
  $lines.Add('## Findings') | Out-Null
  if ($report.findings.Count -eq 0) {
    $lines.Add('- none') | Out-Null
  } else {
  foreach ($finding in $report.findings) {
    $lines.Add(("- [{0}] {1}: {2}" -f $finding.severity, $finding.area, $finding.message)) | Out-Null
  }
  }
  if ($null -ne $report.a010Checkpoint) {
    $lines.Add('') | Out-Null
    $lines.Add('## A-010 Checkpoint') | Out-Null
    if ($report.a010Checkpoint.ok) {
      foreach ($field in @(
        'report',
        'checkpointStatus',
        'snapshotCount',
        'elapsedHours',
        'remainingHours',
        'maxGapHours',
        'gapEventCount',
        'continuousStartAt',
        'continuousElapsedHours',
        'continuousRemainingHours',
        'continuousEta',
        'snapshotsWithGatewayErrors',
        'snapshotsWithOomErrors'
      )) {
        $value = $report.a010Checkpoint | Select-Object -ExpandProperty $field
        $lines.Add(('- {0}: `{1}`' -f $field, $value)) | Out-Null
      }
    } else {
      $lines.Add(('- error: `{0}`' -f $report.a010Checkpoint.error)) | Out-Null
    }
  }
  $lines.Add('') | Out-Null
  $lines.Add('## Command Summary') | Out-Null
  foreach ($cmd in $report.commands) {
    $lines.Add(("- {0}: exit={1}, timedOut={2}" -f $cmd.name, $cmd.exitCode, $cmd.timedOut)) | Out-Null
  }
  $lines | Set-Content -LiteralPath $mdPath -Encoding UTF8

  [pscustomobject]@{
    decision = $report.decision
    json = $jsonPath
    markdown = $mdPath
    findings = $report.findings
  }
}

$iteration = 0
do {
  $iteration++
  $result = New-AuditReport
  Write-Output ("AUDIT_DECISION={0}" -f $result.decision)
  Write-Output ("AUDIT_MARKDOWN={0}" -f $result.markdown)
  Write-Output ("AUDIT_JSON={0}" -f $result.json)

  $continueLoop = ($Iterations -eq 0 -or $iteration -lt $Iterations)
  if ($continueLoop) {
    Start-Sleep -Seconds ([Math]::Max(1, $IntervalMinutes * 60))
  }
} while ($continueLoop)
