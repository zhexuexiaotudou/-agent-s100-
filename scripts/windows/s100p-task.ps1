param(
  [Parameter(Mandatory)]
  [ValidateSet(
    'ssh-smoke',
    'diagnose-nas',
    'repair-nas-runtime',
    'diagnose-openclaw',
    'diagnose-openclaw-health',
    'check-overnight',
    'refresh-baseline-readonly',
    'run-startup-link-check'
  )]
  [string]$Action,

  [string]$ConfigPath,
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
  if ($StandardInput) {
    $normalizedInput = $StandardInput -replace "`r`n", "`n" -replace "`r", "`n"
    $p.StandardInput.Write($normalizedInput)
  }
  $p.StandardInput.Close()

  if (-not $p.WaitForExit($Timeout * 1000)) {
    try { $p.Kill($true) } catch {}
    return New-ProcessResult -ExitCode 124 -Output '' -ErrorText "Timed out after $Timeout seconds" -TimedOut $true
  }

  return New-ProcessResult -ExitCode $p.ExitCode -Output $p.StandardOutput.ReadToEnd() -ErrorText $p.StandardError.ReadToEnd()
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
ss -ltnp 2>/dev/null | grep -E '8765|18080|18789|3000|8080|22' || true
'@
    }
    'diagnose-openclaw-health' {
      return @'
set +e
echo '--- openclaw-health'
curl -i -sS --max-time 5 http://127.0.0.1:8765/api/health | head -20
echo '--- openclaw-ui'
curl -i -sS --max-time 5 http://127.0.0.1:8765/ui | head -20
echo '--- qwen-health'
curl -i -sS --max-time 5 http://127.0.0.1:18080/health | head -20
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
    'refresh-baseline-readonly' {
      return @'
set -e
cd /root/.openclaw/workspace
timeout 45 bash scripts/run_allowlisted_tool.sh baseline_gap_decision_probe
timeout 45 bash scripts/run_allowlisted_tool.sh baseline_acceptance_probe
timeout 45 bash scripts/run_allowlisted_tool.sh baseline_acceptance_trend_probe
timeout 45 bash scripts/run_allowlisted_tool.sh baseline_evidence_manifest_probe
timeout 45 bash scripts/run_allowlisted_tool.sh teacher_baseline_briefing_probe
timeout 30 bash scripts/summarize_overnight_baseline_runner.sh
'@
    }
    default {
      throw "Unsupported remote script: $Name"
    }
  }
}

function Test-RootAction {
  param([string]$Name)
  return @('check-overnight', 'refresh-baseline-readonly') -contains $Name
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
