param(
  [string]$RemoteHost = "sunrise@192.168.127.10",
  [string]$SshKey = "C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519",
  [string]$ReportRoot = "/mnt/nas/openclaw/reports/models",
  [int]$TimeoutSeconds = 3600
)

$ErrorActionPreference = "Stop"

Write-Host "Read-only preflight for queue baseline service..."
ssh.exe -i $SshKey -o BatchMode=yes -o ConnectTimeout=8 $RemoteHost @"
set -e
systemctl is-active dream7b-bpu-batch-queue.service
systemctl is-enabled dream7b-bpu-batch-queue.service
ss -ltn | grep ':18888'
curl -sS --max-time 5 http://127.0.0.1:18888/v1/models
"@

Write-Host "To run a fresh queue baseline telemetry pass, execute the deployed probe on S100P."
Write-Host "This wrapper intentionally does not restart or modify services."
Write-Host "Suggested remote probe:"
Write-Host "  /mnt/nas/openclaw/runtimes/dream7b-bpu-segment-major-default/scripts/probes/dream7b_bpu_segment_major_candidate_service_telemetry_probe.sh"
Write-Host "Report root: $ReportRoot"
