param(
    [string[]]$Segments = @("2:3"),
    [int]$BatchSize = 2,
    [int]$SeqLen = 16,
    [int]$WBits = 8,
    [int]$LmHeadWBits = 0,
    [string]$March = "nash-e",
    [string]$Distro = "DiguaTrueBatchBuilder",
    [string]$WorkspaceRoot = "F:\Project\Digua",
    [string]$ModelDir = "F:\Project\Digua\tmp\true_batch_inputs\dream7b-hf",
    [string]$CompilerPy = "F:\Project\Digua\tmp\wsl_compile_dream_full_forward.py",
    [string]$StageRoot = "F:\Project\Digua\tmp\true_batch_hbm_stage",
    [string]$WslExe = "$env:WINDIR\System32\wsl.exe",
    [string]$RemoteHost = "sunrise@192.168.127.10",
    [string]$SshKey = "C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519",
    [string]$KnownHosts = "C:\Users\zhexu\.ssh\known_hosts",
    [string]$RemoteOutputRoot = "",
    [string]$RemoteReportRoot = "",
    [ValidateSet("full", "last-token")]
    [string]$FinalLogitsMode = "full",
    [int]$StopAfterGB = 100,
    [int]$MinCommitHeadroomGB = 64,
    [int]$WarnProcessPrivateGB = 12,
    [switch]$PreflightOnly,
    [switch]$SkipPreflight,
    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function ConvertTo-WslPath {
    param([Parameter(Mandatory=$true)][string]$Path)
    $full = [System.IO.Path]::GetFullPath($Path)
    if ($full -notmatch '^([A-Za-z]):\\(.*)$') {
        throw "Cannot convert non-drive path to WSL path: $Path"
    }
    $drive = $Matches[1].ToLowerInvariant()
    $rest = $Matches[2] -replace '\\', '/'
    return "/mnt/$drive/$rest"
}

function Invoke-Native {
    param(
        [Parameter(Mandatory=$true)][string]$FilePath,
        [Parameter(Mandatory=$true)][string[]]$Arguments
    )
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $FilePath $($Arguments -join ' ')"
    }
}

function Invoke-WslBash {
    param([Parameter(Mandatory=$true)][string]$Command)
    $args = @("-d", $Distro, "--", "bash", "-lc", $Command)
    for ($attempt = 1; $attempt -le 2; $attempt++) {
        & $WslExe @args
        $exitCode = $LASTEXITCODE
        if ($exitCode -eq 0) {
            return
        }
        if ($exitCode -eq -1 -and $attempt -lt 2) {
            Write-Host "WSL transient failure exit=-1; terminating $Distro and retrying once"
            & $WslExe --terminate $Distro 2>$null
            Start-Sleep -Seconds 3
            continue
        }
        throw "Command failed with exit code ${exitCode}: $WslExe $($args -join ' ')"
    }
}

function Invoke-Remote {
    param([Parameter(Mandatory=$true)][string]$Command)
    $args = @(
        "-i", $SshKey,
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=$KnownHosts",
        $RemoteHost,
        $Command
    )
    & ssh.exe @args 2>&1 | ForEach-Object { Write-Host $_ }
    $exitCode = $LASTEXITCODE
    return [int]$exitCode
}

function Get-CommitInfo {
    $typeName = "NativeMethods.PerformanceInfo"
    if (-not ($typeName -as [type])) {
        Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

namespace NativeMethods {
    [StructLayout(LayoutKind.Sequential)]
    public struct PERFORMANCE_INFORMATION {
        public uint cb;
        public UIntPtr CommitTotal;
        public UIntPtr CommitLimit;
        public UIntPtr CommitPeak;
        public UIntPtr PhysicalTotal;
        public UIntPtr PhysicalAvailable;
        public UIntPtr SystemCache;
        public UIntPtr KernelTotal;
        public UIntPtr KernelPaged;
        public UIntPtr KernelNonpaged;
        public UIntPtr PageSize;
        public uint HandleCount;
        public uint ProcessCount;
        public uint ThreadCount;
    }

    public static class PerformanceInfo {
        [DllImport("psapi.dll", SetLastError = true)]
        public static extern bool GetPerformanceInfo(out PERFORMANCE_INFORMATION info, uint size);
    }
}
"@
    }

    $info = New-Object NativeMethods.PERFORMANCE_INFORMATION
    $ok = [NativeMethods.PerformanceInfo]::GetPerformanceInfo([ref]$info, [System.Runtime.InteropServices.Marshal]::SizeOf([type][NativeMethods.PERFORMANCE_INFORMATION]))
    if (-not $ok) {
        throw "GetPerformanceInfo failed"
    }
    $pageSize = [double]$info.PageSize.ToUInt64()
    $gb = 1024.0 * 1024.0 * 1024.0
    $commitTotalGB = ([double]$info.CommitTotal.ToUInt64() * $pageSize) / $gb
    $commitLimitGB = ([double]$info.CommitLimit.ToUInt64() * $pageSize) / $gb
    $commitPeakGB = ([double]$info.CommitPeak.ToUInt64() * $pageSize) / $gb
    $physicalTotalGB = ([double]$info.PhysicalTotal.ToUInt64() * $pageSize) / $gb
    $physicalAvailableGB = ([double]$info.PhysicalAvailable.ToUInt64() * $pageSize) / $gb
    return [pscustomobject]@{
        CommitTotalGB = [math]::Round($commitTotalGB, 2)
        CommitLimitGB = [math]::Round($commitLimitGB, 2)
        CommitHeadroomGB = [math]::Round($commitLimitGB - $commitTotalGB, 2)
        CommitPeakGB = [math]::Round($commitPeakGB, 2)
        PhysicalTotalGB = [math]::Round($physicalTotalGB, 2)
        PhysicalAvailableGB = [math]::Round($physicalAvailableGB, 2)
    }
}

function Get-DriveFreeGB {
    param([Parameter(Mandatory=$true)][string]$Path)
    $full = [System.IO.Path]::GetFullPath($Path)
    $root = [System.IO.Path]::GetPathRoot($full)
    $drive = New-Object System.IO.DriveInfo($root)
    return [math]::Round($drive.AvailableFreeSpace / 1GB, 2)
}

function Invoke-CompilePreflight {
    $commit = Get-CommitInfo
    $topProcesses = Get-Process |
        Sort-Object PrivateMemorySize64 -Descending |
        Select-Object -First 8 Id,ProcessName,Path,
            @{Name="PrivateGB";Expression={[math]::Round($_.PrivateMemorySize64 / 1GB, 2)}},
            @{Name="WorkingGB";Expression={[math]::Round($_.WorkingSet64 / 1GB, 2)}}
    $largeProcesses = @($topProcesses | Where-Object { $_.PrivateGB -ge $WarnProcessPrivateGB })
    $stageFreeGB = Get-DriveFreeGB $StageRoot
    $modelFreeGB = Get-DriveFreeGB $ModelDir

    Write-Host "preflight_commit_total_gb=$($commit.CommitTotalGB)"
    Write-Host "preflight_commit_limit_gb=$($commit.CommitLimitGB)"
    Write-Host "preflight_commit_headroom_gb=$($commit.CommitHeadroomGB)"
    Write-Host "preflight_commit_peak_gb=$($commit.CommitPeakGB)"
    Write-Host "preflight_physical_available_gb=$($commit.PhysicalAvailableGB)"
    Write-Host "preflight_stage_free_gb=$stageFreeGB"
    Write-Host "preflight_model_drive_free_gb=$modelFreeGB"
    Write-Host "preflight_min_commit_headroom_gb=$MinCommitHeadroomGB"
    Write-Host "preflight_top_private_processes="
    $topProcesses | Format-Table -AutoSize | Out-String | ForEach-Object { Write-Host $_.TrimEnd() }

    if ($largeProcesses.Count -gt 0) {
        Write-Host "preflight_large_private_processes="
        $largeProcesses | Format-Table -AutoSize | Out-String | ForEach-Object { Write-Host $_.TrimEnd() }
    }
    if ($commit.CommitHeadroomGB -lt $MinCommitHeadroomGB) {
        throw "Insufficient Windows commit headroom for true-batch compile: headroom=$($commit.CommitHeadroomGB)GB required=$MinCommitHeadroomGB GB"
    }
}

function New-RemoteDir {
    param([Parameter(Mandatory=$true)][string]$Path)
    $code = Invoke-Remote "mkdir -p '$Path'"
    if ($code -ne 0) {
        throw "Failed to create remote directory: $Path"
    }
}

function Test-RemoteSegmentVerified {
    param([Parameter(Mandatory=$true)][string]$RemoteSegmentDir)
    $cmd = "cd '$RemoteSegmentDir' 2>/dev/null && test -f manifest.sha256 && sha256sum -c manifest.sha256 >/dev/null"
    $code = Invoke-Remote $cmd
    return ($code -eq 0)
}

function Remove-LocalSegmentDir {
    param(
        [Parameter(Mandatory=$true)][string]$Path,
        [bool]$Required = $true
    )
    $resolvedStage = [System.IO.Path]::GetFullPath($StageRoot).TrimEnd('\')
    $resolvedPath = [System.IO.Path]::GetFullPath($Path).TrimEnd('\')
    if (-not $resolvedPath.StartsWith($resolvedStage + "\", [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove path outside stage root: $resolvedPath"
    }
    if (Test-Path -LiteralPath $resolvedPath) {
        try {
            Remove-Item -LiteralPath $resolvedPath -Recurse -Force
        } catch {
            Write-Host "Windows Remove-Item failed for $resolvedPath; retrying through WSL"
            $wslPath = ConvertTo-WslPath $resolvedPath
            try {
                Invoke-WslBash "rm -rf '$wslPath'"
            } catch {
                if ($Required) {
                    throw
                }
                Write-Host "WARNING: best-effort WSL cleanup failed for $resolvedPath"
            }
            if (Test-Path -LiteralPath $resolvedPath) {
                if ($Required) {
                    throw "Failed to remove local stage path after WSL fallback: $resolvedPath"
                }
                Write-Host "WARNING: local stage path remains after best-effort cleanup: $resolvedPath"
            }
        }
    }
}

function Write-StatusRecord {
    param([hashtable]$Record)
    $statusPath = Join-Path $StageRoot "true_batch_compile_status.jsonl"
    New-Item -ItemType Directory -Force -Path $StageRoot | Out-Null
    ($Record | ConvertTo-Json -Compress) | Add-Content -LiteralPath $statusPath -Encoding UTF8
}

if ([string]::IsNullOrWhiteSpace($RemoteOutputRoot)) {
    $RemoteOutputRoot = "/mnt/nas/openclaw/models/dream7b-hbm/true-batch-seq$SeqLen-b$BatchSize"
    if ($FinalLogitsMode -eq "last-token") {
        $RemoteOutputRoot = "${RemoteOutputRoot}-last-token-final"
    }
}
if ([string]::IsNullOrWhiteSpace($RemoteReportRoot)) {
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $RemoteReportRoot = "/mnt/nas/openclaw/reports/models/dream7b_true_batch_compile_$($stamp)_b$BatchSize"
}

foreach ($requiredPath in @($WorkspaceRoot, $ModelDir, $CompilerPy)) {
    if (-not (Test-Path -LiteralPath $requiredPath)) {
        throw "Required path does not exist: $requiredPath"
    }
}
if (-not (Test-Path -LiteralPath $SshKey)) {
    throw "SSH key does not exist: $SshKey"
}
if (-not (Test-Path -LiteralPath $WslExe)) {
    throw "WSL executable does not exist: $WslExe"
}

$modelDirWsl = ConvertTo-WslPath $ModelDir
$compilerPyWsl = ConvertTo-WslPath $CompilerPy
$stageRootWsl = ConvertTo-WslPath $StageRoot
$normalizedSegments = @()
foreach ($segmentArg in $Segments) {
    foreach ($part in ($segmentArg -split '[,\s]+')) {
        if (-not [string]::IsNullOrWhiteSpace($part)) {
            $normalizedSegments += $part
        }
    }
}
if ($normalizedSegments.Count -eq 0) {
    throw "No segments requested"
}
$Segments = $normalizedSegments
$runId = Get-Date -Format "yyyyMMdd-HHmmss"
$producedBytes = [int64]0
$stopAfterBytes = [int64]$StopAfterGB * 1024 * 1024 * 1024

New-Item -ItemType Directory -Force -Path $StageRoot | Out-Null
if (-not $SkipPreflight) {
    Invoke-CompilePreflight
}
if ($PreflightOnly) {
    Write-Host "verdict=preflight_ok"
    return
}
New-RemoteDir $RemoteOutputRoot
New-RemoteDir $RemoteReportRoot

Write-Host "remote_output_root=$RemoteOutputRoot"
Write-Host "remote_report_root=$RemoteReportRoot"
Write-Host "segments=$($Segments -join ' ')"

foreach ($spec in $Segments) {
    if ($spec -notmatch '^(\d+):(\d+)$') {
        throw "Invalid segment spec: $spec"
    }
    $segmentStart = [int]$Matches[1]
    $segmentEnd = [int]$Matches[2]
    if ($segmentEnd -le $segmentStart) {
        throw "Segment end must be greater than start: $spec"
    }
    if ($FinalLogitsMode -ne "full" -and -not ($segmentStart -eq 27 -and $segmentEnd -eq 28)) {
        throw "FinalLogitsMode '$FinalLogitsMode' is only valid for final segment 27:28"
    }

    $segmentName = "seg{0:D2}_{1:D2}" -f $segmentStart, $segmentEnd
    $localSegmentDir = Join-Path $StageRoot $segmentName
    $localLogDir = Join-Path $StageRoot "logs"
    $localLogPath = Join-Path $localLogDir ("compile_{0}_b{1}_{2}.log" -f $segmentName, $BatchSize, $runId)
    $localRunner = Join-Path $StageRoot ("run_{0}_b{1}_{2}.sh" -f $segmentName, $BatchSize, $runId)
    $remoteSegmentDir = "$RemoteOutputRoot/$segmentName"
    $baseName = "dream7b_segment_${segmentStart}_${segmentEnd}_seq${SeqLen}_b${BatchSize}_q${WBits}"
    $compilerExtraArgs = ""
    if ($LmHeadWBits -ne 0 -and $LmHeadWBits -ne $WBits) {
        $baseName = "${baseName}_lmheadq${LmHeadWBits}"
        $compilerExtraArgs += " --lm-head-w-bits '$LmHeadWBits'"
    }
    if ($FinalLogitsMode -ne "full") {
        $baseName = "${baseName}_last_token_logits"
        $compilerExtraArgs += " --final-logits-mode '$FinalLogitsMode'"
    }

    if ((-not $Force) -and $FinalLogitsMode -eq "full") {
        if (Test-RemoteSegmentVerified $remoteSegmentDir) {
            Write-Host "SKIP verified remote segment: $segmentName"
            Write-StatusRecord @{
                time = (Get-Date).ToString("o")
                run_id = $runId
                segment = $segmentName
                status = "skipped_verified_remote"
                remote_segment_dir = $remoteSegmentDir
            }
            Remove-LocalSegmentDir $localSegmentDir -Required $false
            continue
        }
    }

    New-Item -ItemType Directory -Force -Path $localLogDir | Out-Null
    Remove-LocalSegmentDir $localSegmentDir
    New-Item -ItemType Directory -Force -Path $localSegmentDir | Out-Null

    $localSegmentWsl = ConvertTo-WslPath $localSegmentDir
    $localLogWsl = ConvertTo-WslPath $localLogPath
    $runnerWsl = ConvertTo-WslPath $localRunner

    $runner = @"
#!/usr/bin/env bash
set -euo pipefail
mkdir -p '$localSegmentWsl' '$(ConvertTo-WslPath $localLogDir)'
source /opt/digua/dream-true-batch-venv/bin/activate
python -X faulthandler '$compilerPyWsl' \
  --model-dir '$modelDirWsl' \
  --output-dir '$localSegmentWsl' \
  --seq-len '$SeqLen' \
  --batch-size '$BatchSize' \
  --segment-start '$segmentStart' \
  --segment-end '$segmentEnd' \
  --dtype float32 \
  --march '$March' \
  --w-bits '$WBits'$compilerExtraArgs 2>&1 | tee '$localLogWsl'
python - <<'PY'
from hbdk4.compiler import link
from hbdk4.compiler.hbm import Hbo
from pathlib import Path
base = Path("$localSegmentWsl")
hbo_path = base / "$baseName.hbo"
hbm_path = base / "$baseName.hbm"
if not hbo_path.exists():
    raise SystemExit(f"missing HBO: {hbo_path}")
link([Hbo(str(hbo_path))], str(hbm_path))
print(f"HBM: {hbm_path}")
print(f"HBM_SIZE: {hbm_path.stat().st_size}")
PY
cd '$localSegmentWsl'
sha256sum '$baseName.bc' '${baseName}_convert.bc' '${baseName}_convert_removed.bc' '$baseName.hbo' '$baseName.hbm' > manifest.sha256
sha256sum -c manifest.sha256
du -sb .
"@
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($localRunner, $runner, $utf8NoBom)

    Write-Host "COMPILE $segmentName"
    Invoke-WslBash "bash '$runnerWsl'"

    $segmentBytes = (Get-ChildItem -LiteralPath $localSegmentDir -Recurse -File | Measure-Object -Property Length -Sum).Sum
    if ($null -eq $segmentBytes) {
        throw "No files produced for $segmentName"
    }
    $producedBytes += [int64]$segmentBytes

    $hbmPath = Join-Path $localSegmentDir "$baseName.hbm"
    $manifestPath = Join-Path $localSegmentDir "manifest.sha256"
    if (-not (Test-Path -LiteralPath $hbmPath)) {
        throw "Missing HBM after compile: $hbmPath"
    }
    if (-not (Test-Path -LiteralPath $manifestPath)) {
        throw "Missing manifest after compile: $manifestPath"
    }

    Write-Host "SYNC $segmentName -> NAS"
    $scpArgs = @(
        "-r",
        "-i", $SshKey,
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=$KnownHosts",
        $localSegmentDir,
        "${RemoteHost}:$RemoteOutputRoot/"
    )
    Invoke-Native "scp.exe" $scpArgs

    $scpLogArgs = @(
        "-i", $SshKey,
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=$KnownHosts",
        $localLogPath,
        "${RemoteHost}:$RemoteReportRoot/"
    )
    Invoke-Native "scp.exe" $scpLogArgs

    Write-Host "VERIFY remote $segmentName"
    $verifyCode = Invoke-Remote "cd '$remoteSegmentDir' && sha256sum -c manifest.sha256"
    if ($verifyCode -ne 0) {
        throw "Remote sha256 verification failed for $segmentName"
    }

    Write-StatusRecord @{
        time = (Get-Date).ToString("o")
        run_id = $runId
        segment = $segmentName
        status = "compiled_synced_verified"
        bytes = [int64]$segmentBytes
        remote_segment_dir = $remoteSegmentDir
        remote_report_root = $RemoteReportRoot
    }

    Write-Host "CLEAN local stage $segmentName"
    Remove-LocalSegmentDir $localSegmentDir -Required $false

    if ($producedBytes -ge $stopAfterBytes) {
        Write-Host "STOP_AFTER_GB reached: $StopAfterGB"
        break
    }
}

Write-Host "verdict=finished"
