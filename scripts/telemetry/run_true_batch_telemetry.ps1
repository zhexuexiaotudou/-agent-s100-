param(
  [string]$RemoteHost = "sunrise@192.168.127.10",
  [string]$SshKey = "C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519",
  [string]$HbmRoot = "/mnt/nas/openclaw/models/dream7b-hbm/true-batch-seq16-b4",
  [string]$ReportRoot = "/mnt/nas/openclaw/reports/models",
  [int]$MicrobatchCount = 1536,
  [int]$BatchSize = 4,
  [string]$Groups = "0:6,6:12,12:18,18:24,24:28"
)

$ErrorActionPreference = "Stop"

Write-Host "Read-only preflight for true-batch artifacts..."
ssh.exe -i $SshKey -o BatchMode=yes -o ConnectTimeout=8 $RemoteHost @"
set -e
test -d '$HbmRoot'
find '$HbmRoot' -maxdepth 1 -type d -name 'seg[0-9][0-9]_[0-9][0-9]' | wc -l
test -f '$HbmRoot/seg00_01/manifest.sha256'
test -f '$HbmRoot/seg27_28/manifest.sha256'
"@

Write-Host "Suggested remote true-batch telemetry command:"
Write-Host "python3 /mnt/nas/openclaw/scripts/probes/dream7b_true_batch_group_major_telemetry_probe.py --hbm-root $HbmRoot --report-root $ReportRoot --groups '$Groups' --microbatch-count $MicrobatchCount --batch-size $BatchSize --inner-order segment-major"
Write-Host "This wrapper does not change production service or port 18888."
