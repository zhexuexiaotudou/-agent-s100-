param(
  [Parameter(Mandatory)]
  [ValidateSet(
    'ssh-smoke',
    'diagnose-nas',
    'repair-nas-runtime',
    'diagnose-openclaw',
    'check-overnight',
    'validate-baseline-scripts-readonly',
    'refresh-a010-local-readonly',
    'read-a010-latest-checkpoint-json',
    'read-remote-report-file',
    'refresh-baseline-readonly',
    'refresh-baseline-local-readonly',
    'run-startup-link-check'
  )]
  [string]$Action,

  [string]$ConfigPath,
  [string]$RemotePath,
  [int]$MaxLines = 240,
  [int]$TimeoutSeconds = 90,
  [switch]$Json
)

$ErrorActionPreference = 'Stop'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir '..\..')
if (-not $ConfigPath) {
  $ConfigPath = Join-Path $RepoRoot 'scripts\startup_link_check\link-check.config.json'
}

function Read-Config {
  if (-not (Test-Path -LiteralPath $ConfigPath)) {
    throw "Missing config: $ConfigPath"
  }
  return Get-Content -LiteralPath $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
}

function New-ProcessResult {
  param(
    [int]$ExitCode,
    [string]$Output,
    [string]$ErrorText,
    [bool]$TimedOut = $false
  )
  [pscustomobject]@{
    exitCode = $ExitCode
    timedOut = $TimedOut
    output = $Output
    error = $ErrorText
  }
}

function Invoke-External {
  param(
    [Parameter(Mandatory)][string]$FilePath,
    [string[]]$Arguments = @(),
    [string]$StandardInput = '',
    [int]$Timeout = 90
  )
  $psi = [System.Diagnostics.ProcessStartInfo]::new()
  $psi.FileName = $FilePath
  $psi.Arguments = (($Arguments | ForEach-Object { ConvertTo-CommandLineArgument $_ }) -join ' ')
  $psi.RedirectStandardOutput = $true
  $psi.RedirectStandardError = $true
  $psi.RedirectStandardInput = $true
  $psi.UseShellExecute = $false
  $psi.CreateNoWindow = $true

  $p = [System.Diagnostics.Process]::new()
  $p.StartInfo = $psi
  [void]$p.Start()
  $stdoutTask = $p.StandardOutput.ReadToEndAsync()
  $stderrTask = $p.StandardError.ReadToEndAsync()
  if ($StandardInput) {
    $p.StandardInput.Write($StandardInput)
  }
  $p.StandardInput.Close()

  if (-not $p.WaitForExit($Timeout * 1000)) {
    try { $p.Kill($true) } catch {}
    try { $p.WaitForExit(5000) | Out-Null } catch {}
    $partialOutput = ''
    $partialError = "Timed out after $Timeout seconds"
    if ($stdoutTask.IsCompleted) { $partialOutput = $stdoutTask.Result }
    if ($stderrTask.IsCompleted -and $stderrTask.Result) { $partialError = $partialError + [Environment]::NewLine + $stderrTask.Result }
    return New-ProcessResult -ExitCode 124 -Output $partialOutput -ErrorText $partialError -TimedOut $true
  }

  try { $p.WaitForExit() } catch {}
  return New-ProcessResult -ExitCode $p.ExitCode -Output $stdoutTask.Result -ErrorText $stderrTask.Result
}

function ConvertTo-CommandLineArgument {
  param([AllowNull()][string]$Argument)
  if ($null -eq $Argument) { return '""' }
  if ($Argument -notmatch '[\s"]') { return $Argument }
  $escaped = $Argument -replace '\\', '\\' -replace '"', '\"'
  return '"' + $escaped + '"'
}

function Invoke-S100PBash {
  param(
    [Parameter(Mandatory)][string]$Script,
    [int]$Timeout = 90,
    [switch]$RunAsRoot
  )
  $cfg = Read-Config
  $ssh = 'C:\Windows\System32\OpenSSH\ssh.exe'
  $target = '{0}@{1}' -f $cfg.s100p.user, $cfg.s100p.host
  $remoteShell = if ($RunAsRoot) { @('sudo', '-n', 'bash', '-s') } else { @('bash', '-s') }
  $args = @(
    '-i', $cfg.s100p.sshKey,
    '-o', 'BatchMode=yes',
    '-o', ('ConnectTimeout={0}' -f $cfg.s100p.sshConnectTimeoutSeconds),
    '-o', 'StrictHostKeyChecking=accept-new',
    $target
  ) + $remoteShell
  return Invoke-External -FilePath $ssh -Arguments $args -StandardInput $Script -Timeout $Timeout
}

function Write-Result {
  param([pscustomobject]$Result)
  if ($Json) {
    $Result | ConvertTo-Json -Depth 8
    return
  }
  if ($Result.output) { Write-Output $Result.output.TrimEnd() }
  if ($Result.error) { Write-Error -Message $Result.error.TrimEnd() -ErrorAction Continue }
  exit $Result.exitCode
}

function Get-RemoteScript {
  param([string]$Name)

  switch ($Name) {
    'ssh-smoke' {
      return @'
set -e
echo S100P_SSH_OK
hostname
whoami
date -Is
'@
    }
    'diagnose-nas' {
      return @'
set +e
echo '--- identity'
hostname
whoami
date -Is
echo '--- eth0'
timeout 3 ip -br link show eth0
timeout 3 ip -4 addr show dev eth0
echo '--- route'
timeout 3 ip route get 169.254.110.209
timeout 3 ip route
echo '--- neighbor'
timeout 3 ip neigh show dev eth0 || true
echo '--- ping'
timeout 5 ping -c 2 -W 1 -I eth0 169.254.110.209 || true
echo '--- nfs-mount'
timeout 5 findmnt /mnt/nas/openclaw || true
timeout 3 grep -E '169.254.110.209|/mnt/nas/openclaw' /proc/mounts || true
echo '--- directory'
timeout 4 ls -ld /mnt /mnt/nas /mnt/nas/openclaw 2>&1 || true
echo '--- openclaw'
sudo -n env XDG_RUNTIME_DIR=/run/user/0 systemctl --user is-active openclaw-gateway.service 2>/dev/null || true
'@
    }
    'repair-nas-runtime' {
      return @'
set +e
echo '--- before'
ip -br link show eth0
ip -4 addr show dev eth0
ip neigh show dev eth0 || true
sudo -n ip neigh flush dev eth0 >/dev/null 2>&1 || true
sudo -n ip link set eth0 down || true
sleep 2
sudo -n ip link set eth0 up || true
sleep 4
sudo -n ip addr replace 169.254.8.10/16 dev eth0 || true
sudo -n ip route replace 169.254.0.0/16 dev eth0 src 169.254.8.10 metric 101 || true
echo '--- after'
ip -br link show eth0
ip -4 addr show dev eth0
ip route get 169.254.110.209 || true
ping -c 2 -W 1 -I eth0 169.254.110.209 || true
ip neigh show dev eth0 || true
'@
    }
    'diagnose-openclaw' {
      return @'
set +e
echo '--- service'
sudo -n env XDG_RUNTIME_DIR=/run/user/0 systemctl --user status openclaw-gateway.service --no-pager -l 2>&1 | tail -80
echo '--- logs'
sudo -n env XDG_RUNTIME_DIR=/run/user/0 journalctl --user -u openclaw-gateway.service --no-pager -n 120 2>&1 |
  grep -Ei 'ws client ready|received message|dispatch complete|EAI_AGAIN|open.feishu.cn|99991672|error|warn' |
  tail -80 || true
echo '--- listeners'
ss -ltnp 2>/dev/null | grep -E '18789|3000|8080|22' || true
'@
    }
    'check-overnight' {
      return @'
set +e
timeout 20 bash /root/.openclaw/workspace/scripts/check_overnight_baseline_runner.sh || echo check_overnight_baseline_runner_timeout_or_failed
timeout 20 bash /root/.openclaw/workspace/scripts/check_overnight_queue.sh || echo check_overnight_queue_timeout_or_failed
timeout 20 bash /root/.openclaw/workspace/scripts/summarize_overnight_baseline_runner.sh || echo summarize_overnight_baseline_runner_timeout_or_failed
echo '--- processes'
ps -eo pid,etime,cmd | grep -E 'overnight_baseline_runner|queue_next_overnight|start_overnight' | grep -v grep || true
'@
    }
    'validate-baseline-scripts-readonly' {
      return @'
set -e
cd /root/.openclaw/workspace
python3 -m json.tool scripts/tool_allowlist.json >/dev/null
bash -n scripts/run_allowlisted_tool.sh
while IFS= read -r script_path; do
  bash -n "$script_path"
done < <(find scripts/probes -maxdepth 1 -type f -name '*.sh' | sort)
echo REMOTE_BASELINE_SCRIPT_VALIDATION_OK
'@
    }
    'refresh-baseline-readonly' {
      return @'
set -e
cd /root/.openclaw/workspace
timeout 45 bash scripts/run_allowlisted_tool.sh baseline_gap_decision_probe
timeout 45 bash scripts/run_allowlisted_tool.sh teacher_baseline_briefing_probe
timeout 45 bash scripts/run_allowlisted_tool.sh baseline_acceptance_probe
timeout 45 bash scripts/run_allowlisted_tool.sh baseline_acceptance_trend_probe
timeout 45 bash scripts/run_allowlisted_tool.sh baseline_evidence_manifest_probe
timeout 30 bash scripts/summarize_overnight_baseline_runner.sh
'@
    }
    'refresh-a010-local-readonly' {
      return @'
set -e
cd /root/.openclaw/workspace
mkdir -p logs/probes reports/stability reports/baseline-status reports/teacher
timeout 45 bash scripts/run_allowlisted_tool.sh stability_snapshot_probe /root/.openclaw/workspace/logs/probes
timeout 45 bash scripts/run_allowlisted_tool.sh stability_summary_probe /root/.openclaw/workspace/logs/probes /root/.openclaw/workspace/reports/stability
timeout 45 bash scripts/run_allowlisted_tool.sh stability_checkpoint_probe /root/.openclaw/workspace/logs/probes /root/.openclaw/workspace/reports/stability 168 2
timeout 45 bash scripts/run_allowlisted_tool.sh baseline_status_probe /root/.openclaw/workspace /root/.openclaw/workspace/reports/baseline-status
timeout 45 bash scripts/run_allowlisted_tool.sh baseline_acceptance_probe /root/.openclaw/workspace /root/.openclaw/workspace/reports/baseline-status
timeout 45 bash scripts/run_allowlisted_tool.sh baseline_acceptance_trend_probe /root/.openclaw/workspace /root/.openclaw/workspace/reports/baseline-status
timeout 45 bash scripts/run_allowlisted_tool.sh baseline_next_action_queue_probe /root/.openclaw/workspace /root/.openclaw/workspace/reports/baseline-status continue-non-nas-readonly-only
timeout 45 bash scripts/run_allowlisted_tool.sh baseline_evidence_manifest_probe /root/.openclaw/workspace /root/.openclaw/workspace/reports/baseline-status
'@
    }
    'read-a010-latest-checkpoint-json' {
      return @'
set -e
latest="$(ls -t /root/.openclaw/workspace/reports/stability/stability_checkpoint_*.json 2>/dev/null | head -1 || true)"
if [ -z "$latest" ]; then
  echo '{"error":"missing_stability_checkpoint"}'
  exit 3
fi
cat "$latest"
'@
    }
    'read-remote-report-file' {
      if (-not $RemotePath) {
        throw 'RemotePath is required for read-remote-report-file'
      }
      $allowedPrefixes = @(
        '/root/.openclaw/workspace/reports/',
        '/root/.openclaw/workspace/logs/probes/'
      )
      $isAllowed = $false
      foreach ($prefix in $allowedPrefixes) {
        if ($RemotePath.StartsWith($prefix, [StringComparison]::Ordinal)) {
          $isAllowed = $true
        }
      }
      if (-not $isAllowed) {
        throw "RemotePath is outside approved report/log prefixes: $RemotePath"
      }
      if ($RemotePath -match '\.\.|[^A-Za-z0-9_./-]') {
        throw "RemotePath contains unsupported characters: $RemotePath"
      }
      if ($MaxLines -lt 1 -or $MaxLines -gt 1000) {
        throw 'MaxLines must be between 1 and 1000'
      }
      return @"
set -e
path='$RemotePath'
max_lines='$MaxLines'
if [ ! -f "`$path" ]; then
  echo "missing_remote_file: `$path" >&2
  exit 4
fi
sed -n "1,`${max_lines}p" "`$path"
"@
    }
    'refresh-baseline-local-readonly' {
      return @'
set -e
cd /root/.openclaw/workspace
  mkdir -p logs/probes reports/models reports/baseline-status reports/teacher reports/security reports/daily-summary reports/stability reports/browser-smoke reports/robot-datasets reports/review-gates reports/external-inputs reports/infrastructure
  if [ -d /root/.openclaw/workspace/documents ]; then
    timeout 45 bash scripts/run_allowlisted_tool.sh index_documents /root/.openclaw/workspace/documents /root/.openclaw/workspace/reports
    timeout 45 bash scripts/run_allowlisted_tool.sh document_daily_summary_probe /root/.openclaw/workspace/documents /root/.openclaw/workspace/reports/daily-summary
  fi
  timeout 45 bash scripts/run_allowlisted_tool.sh nas_link_blocker_probe /root/.openclaw/workspace/logs/probes 169.254.110.209
  timeout 45 bash scripts/run_allowlisted_tool.sh stability_snapshot_probe /root/.openclaw/workspace/logs/probes
  timeout 45 bash scripts/run_allowlisted_tool.sh stability_summary_probe /root/.openclaw/workspace/logs/probes /root/.openclaw/workspace/reports/stability
  timeout 45 bash scripts/run_allowlisted_tool.sh stability_checkpoint_probe /root/.openclaw/workspace/logs/probes /root/.openclaw/workspace/reports/stability 168 2
  timeout 90 bash scripts/run_allowlisted_tool.sh browser_smoke_probe /root/.openclaw/workspace/reports/browser-smoke
  timeout 45 bash scripts/run_allowlisted_tool.sh dataset_card_inventory_probe /root/.openclaw/workspace/robot_datasets /root/.openclaw/workspace/reports/robot-datasets
  timeout 45 bash scripts/run_allowlisted_tool.sh rosbag_named_capture_request_probe /root/.openclaw/workspace/reports/rosbag
  timeout 45 bash scripts/run_allowlisted_tool.sh security_audit_probe /root/.openclaw/workspace/logs/probes
timeout 45 bash scripts/run_allowlisted_tool.sh service_policy_probe /root/.openclaw/workspace/logs/probes
timeout 45 bash scripts/run_allowlisted_tool.sh service_hardening_plan_probe /root/.openclaw/workspace/logs/probes
timeout 45 bash scripts/run_allowlisted_tool.sh service_convergence_decision_probe /root/.openclaw/workspace/logs/probes /root/.openclaw/workspace/reports/security
timeout 45 bash scripts/run_allowlisted_tool.sh service_confirmation_template_probe /root/.openclaw/workspace/reports/security
timeout 45 bash scripts/run_allowlisted_tool.sh service_execution_preflight_probe /root/.openclaw/workspace/reports/security /root/.openclaw/workspace/config/service_convergence_confirmations.json
timeout 45 bash scripts/run_allowlisted_tool.sh sandbox_status_probe /root/.openclaw/workspace/logs/probes
timeout 45 bash scripts/run_allowlisted_tool.sh sandbox_isolation_smoke_probe /root/.openclaw/workspace/logs/probes
timeout 45 bash scripts/run_allowlisted_tool.sh infrastructure_gate_probe /root/.openclaw/workspace /root/.openclaw/workspace/reports/infrastructure
timeout 45 bash scripts/run_allowlisted_tool.sh dream7b_readiness_probe /root/.openclaw/workspace/reports/models
timeout 45 bash scripts/run_allowlisted_tool.sh dream7b_config_template_probe /root/.openclaw/workspace/reports/models
timeout 45 bash scripts/run_allowlisted_tool.sh home_assistant_config_template_probe /root/.openclaw/workspace/reports/home-assistant
  timeout 45 bash scripts/run_allowlisted_tool.sh home_assistant_status_probe /root/.openclaw/workspace/logs/probes
  timeout 45 bash scripts/run_allowlisted_tool.sh external_input_gate_probe /root/.openclaw/workspace /root/.openclaw/workspace/reports/external-inputs
  timeout 45 bash scripts/run_allowlisted_tool.sh control_action_template_probe /root/.openclaw/workspace/reports/control
  timeout 45 bash scripts/run_allowlisted_tool.sh control_action_policy_probe /root/.openclaw/workspace/logs/probes
  timeout 45 bash scripts/run_allowlisted_tool.sh operator_review_gate_probe /root/.openclaw/workspace /root/.openclaw/workspace/reports/review-gates
  timeout 45 bash scripts/run_allowlisted_tool.sh log_diagnose /root/.openclaw/workspace/logs /root/.openclaw/workspace/logs/probes
  timeout 45 bash scripts/run_allowlisted_tool.sh experiment_report_probe /root/.openclaw/workspace/reports/experiments
  timeout 45 bash scripts/run_allowlisted_tool.sh baseline_status_probe /root/.openclaw/workspace /root/.openclaw/workspace/reports/baseline-status
timeout 45 bash scripts/run_allowlisted_tool.sh baseline_gap_decision_probe /root/.openclaw/workspace /root/.openclaw/workspace/reports/baseline-status
timeout 45 bash scripts/run_allowlisted_tool.sh teacher_baseline_briefing_probe /root/.openclaw/workspace /root/.openclaw/workspace/reports/teacher
timeout 45 bash scripts/run_allowlisted_tool.sh baseline_acceptance_probe /root/.openclaw/workspace /root/.openclaw/workspace/reports/baseline-status
timeout 45 bash scripts/run_allowlisted_tool.sh baseline_acceptance_trend_probe /root/.openclaw/workspace /root/.openclaw/workspace/reports/baseline-status
timeout 45 bash scripts/run_allowlisted_tool.sh baseline_next_action_queue_probe /root/.openclaw/workspace /root/.openclaw/workspace/reports/baseline-status continue-non-nas-readonly-only
timeout 45 bash scripts/run_allowlisted_tool.sh baseline_evidence_manifest_probe /root/.openclaw/workspace /root/.openclaw/workspace/reports/baseline-status
'@
    }
    default {
      throw "Unsupported remote script: $Name"
    }
  }
}

function Test-RootAction {
  param([string]$Name)
  return @('check-overnight', 'validate-baseline-scripts-readonly', 'refresh-a010-local-readonly', 'read-a010-latest-checkpoint-json', 'read-remote-report-file', 'refresh-baseline-readonly', 'refresh-baseline-local-readonly') -contains $Name
}

if ($Action -eq 'run-startup-link-check') {
  $startup = Join-Path $RepoRoot 'scripts\startup_link_check\S100P-NAS-LinkCheck.ps1'
  $result = Invoke-External -FilePath 'powershell.exe' -Arguments @(
    '-ExecutionPolicy', 'Bypass',
    '-File', $startup,
    '-NoGui',
    '-NoDelay'
  ) -Timeout $TimeoutSeconds
  Write-Result $result
}

$remoteScript = Get-RemoteScript -Name $Action
$remoteResult = Invoke-S100PBash -Script $remoteScript -Timeout $TimeoutSeconds -RunAsRoot:(Test-RootAction -Name $Action)
Write-Result $remoteResult
