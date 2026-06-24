param(
  [string]$OutputRoot = "tmp\cloud_compile_bundle",
  [string]$BundleName = ""
)

$ErrorActionPreference = "Stop"

if (-not $BundleName) {
  $BundleName = "dream7b_cloud_bundle_{0}" -f (Get-Date -Format "yyyyMMdd-HHmmss")
}

$repo = (Resolve-Path ".").Path
$bundle = Join-Path $repo (Join-Path $OutputRoot $BundleName)
$scriptsDir = Join-Path $bundle "scripts\probes"
$docsDir = Join-Path $bundle "docs"
$tmpDir = Join-Path $bundle "tmp"
New-Item -ItemType Directory -Force -Path $scriptsDir, $docsDir, $tmpDir | Out-Null

$files = @(
  "scripts\probes\dream7b_cloud_bootstrap.sh",
  "scripts\probes\dream7b_cloud_gate_runner.sh",
  "scripts\probes\dream7b_cloud_parallel_segments.sh",
  "scripts\probes\dream7b_cloud_resource_monitor.sh",
  "scripts\probes\compile_dream_true_batch_segments.sh",
  "scripts\probes\compile_dream_with_deepseek_skeleton.sh",
  "scripts\probes\dream7b_true_batch_compile_segments_wsl.sh",
  "scripts\probes\dream7b_true_batch_single_segment_runtime_probe.py",
  "scripts\probes\dream7b_bpu_quality_validation_common.py",
  "scripts\probes\dream7b_bpu_quality_logits_diagnostics.py",
  "scripts\probes\dream7b_bpu_quality_generation_quality.py",
  "tmp\wsl_compile_dream_full_forward.py",
  "docs\dream7b_cloud_seq128_execution_plan_2026-06-23.md",
  "docs\dream7b_seq128_cloud_compile_closure_2026-06-23.md",
  "docs\dream7b_bpu_seq16_quality_root_cause_2026-06-22.md",
  "docs\dream7b_bpu_logits_diagnosis_2026-06-22.md",
  "docs\dream7b_s100p_next_work_runbook.md"
)

$manifest = @()
foreach ($rel in $files) {
  $src = Join-Path $repo $rel
  if (-not (Test-Path -LiteralPath $src)) {
    throw "Missing required bundle file: $rel"
  }
  $dst = Join-Path $bundle $rel
  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dst) | Out-Null
  Copy-Item -LiteralPath $src -Destination $dst -Force
  $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $src).Hash.ToLowerInvariant()
  $manifest += [pscustomobject]@{
    path = $rel.Replace("\", "/")
    sha256 = $hash
    bytes = (Get-Item -LiteralPath $src).Length
  }
}

$manifestPath = Join-Path $bundle "SHA256MANIFEST.json"
$manifest | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $manifestPath -Encoding UTF8

$readme = @(
  "# Dream7B Cloud Compile Bundle",
  "",
  ("Generated: {0}" -f (Get-Date -Format o)),
  "",
  "Upload example after the cloud host is ready:",
  "",
  "````powershell",
  ("scp -i C:\Users\zhexu\Downloads\tudou.pem {0}.tar.gz root@<PUBLIC_IP>:/data/dream7b-cloud/input/" -f $BundleName),
  "````",
  "",
  "On the cloud host:",
  "",
  "````bash",
  "mkdir -p /data/dream7b-cloud/bundle",
  ("tar -xzf /data/dream7b-cloud/input/{0}.tar.gz -C /data/dream7b-cloud/bundle --strip-components=1" -f $BundleName),
  "bash /data/dream7b-cloud/bundle/scripts/probes/dream7b_cloud_bootstrap.sh",
  "````"
) -join "`n"
$readme | Set-Content -LiteralPath (Join-Path $bundle "README.md") -Encoding UTF8

$tarPath = Join-Path (Join-Path $repo $OutputRoot) "$BundleName.tar.gz"
if (Get-Command tar.exe -ErrorAction SilentlyContinue) {
  Push-Location (Split-Path -Parent $bundle)
  try {
    tar.exe -czf $tarPath (Split-Path -Leaf $bundle)
  } finally {
    Pop-Location
  }
}

[pscustomobject]@{
  bundle_dir = $bundle
  tar_path = if (Test-Path -LiteralPath $tarPath) { $tarPath } else { $null }
  manifest = $manifestPath
  file_count = $manifest.Count
} | ConvertTo-Json -Depth 4
