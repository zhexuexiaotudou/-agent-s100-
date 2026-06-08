#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
hbm_dir="${DREAM7B_BPU_RESPLIT_HBM_DIR:-/mnt/nas/openclaw/models/dream7b-hbm/resplit-seq16}"
expected_specs="${DREAM7B_BPU_RESPLIT_EXPECTED_SPECS:-0:1 1:2 10:12 12:14 17:19 19:21 26:27 27:28}"
verify_manifest="${DREAM7B_BPU_RESPLIT_VERIFY_MANIFEST:-1}"

case "$report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_root" >&2
    exit 2
    ;;
esac

case "$hbm_dir" in
  /mnt/nas/openclaw/models/dream7b-hbm/resplit-seq16|/mnt/nas/openclaw/models/dream7b-hbm/resplit-seq16/|/home/sunrise/.cache/openclaw/dream7b-hbm/resplit-seq16|/home/sunrise/.cache/openclaw/dream7b-hbm/resplit-seq16/|/tmp/dream7b-hbm/resplit-seq16|/tmp/dream7b-hbm/resplit-seq16/) ;;
  *)
    echo "Refusing resplit HBM path outside approved Dream 7B resplit directories: $hbm_dir" >&2
    exit 2
    ;;
esac

case "$verify_manifest" in
  0|1) ;;
  *)
    echo "DREAM7B_BPU_RESPLIT_VERIFY_MANIFEST must be 0 or 1." >&2
    exit 2
    ;;
esac

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_resplit_hbm_artifact_inventory_$stamp"
mkdir -p "$run_dir"

python3 - \
  "$run_dir" \
  "$hbm_dir" \
  "$expected_specs" \
  "$verify_manifest" <<'PY'
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

run_dir = Path(sys.argv[1])
hbm_dir = Path(sys.argv[2])
expected_specs = sys.argv[3].split()
verify_manifest = sys.argv[4] == "1"

errors = []
warnings = []


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_manifest(path):
    entries = {}
    if not path.is_file():
        return entries
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) >= 2:
            entries[parts[1]] = parts[0]
    return entries


def parse_spec(spec):
    if ":" not in spec:
        raise ValueError(f"invalid spec: {spec}")
    start_text, end_text = spec.split(":", 1)
    start = int(start_text)
    end = int(end_text)
    if start >= end:
        raise ValueError(f"invalid spec bounds: {spec}")
    return start, end


manifest_path = hbm_dir / "manifest.sha256"
manifest = read_manifest(manifest_path)
if not hbm_dir.is_dir():
    errors.append(f"missing resplit HBM directory: {hbm_dir}")
if not manifest_path.is_file():
    errors.append(f"missing manifest: {manifest_path}")

inventory = []
manifest_verified_count = 0
for spec in expected_specs:
    try:
        start, end = parse_spec(spec)
    except Exception as exc:
        errors.append(str(exc))
        continue
    rel_path = Path(f"seg{start:02d}_{end:02d}") / f"dream7b_segment_{start}_{end}_seq16_q8.hbm"
    path = hbm_dir / rel_path
    exists = path.is_file()
    size_bytes = path.stat().st_size if exists else 0
    expected_sha256 = manifest.get(rel_path.as_posix())
    actual_sha256 = ""
    sha256_ok = False
    if not exists:
        errors.append(f"missing resplit HBM: {path}")
    if not expected_sha256:
        errors.append(f"manifest missing entry: {rel_path.as_posix()}")
    if verify_manifest and exists and expected_sha256:
        actual_sha256 = sha256_file(path)
        sha256_ok = actual_sha256 == expected_sha256
        if sha256_ok:
            manifest_verified_count += 1
        else:
            errors.append(f"manifest sha256 mismatch: {path}")
    inventory.append(
        {
            "spec": spec,
            "segment": f"seg{start:02d}_{end:02d}",
            "layer_start": start,
            "layer_end": end,
            "layer_count": end - start,
            "relative_path": rel_path.as_posix(),
            "path": str(path),
            "exists": exists,
            "size_bytes": size_bytes,
            "expected_sha256": expected_sha256 or "",
            "actual_sha256": actual_sha256,
            "sha256_ok": sha256_ok,
        }
    )

unexpected_hbm = sorted(
    str(path.relative_to(hbm_dir))
    for path in hbm_dir.glob("**/*.hbm")
    if path.is_file()
    and str(path.relative_to(hbm_dir)).replace("\\", "/")
    not in {item["relative_path"] for item in inventory}
)
if unexpected_hbm:
    warnings.append(f"unexpected resplit HBM files: {unexpected_hbm}")

total_hbm_size_bytes = sum(item["size_bytes"] for item in inventory if item["exists"])
payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_bpu_resplit_hbm_artifact_inventory_probe" if not errors else "failed_dream7b_bpu_resplit_hbm_artifact_inventory_probe",
    "run_dir": str(run_dir),
    "hbm_dir": str(hbm_dir),
    "expected_specs": expected_specs,
    "expected_hbm_count": len(expected_specs),
    "existing_hbm_count": sum(1 for item in inventory if item["exists"]),
    "manifest_path": str(manifest_path),
    "manifest_entry_count": len(manifest),
    "manifest_verified_count": manifest_verified_count,
    "verify_manifest": verify_manifest,
    "total_hbm_size_bytes": total_hbm_size_bytes,
    "total_hbm_size_gib": round(total_hbm_size_bytes / 1073741824.0, 6),
    "inventory": inventory,
    "unexpected_hbm": unexpected_hbm,
    "next_optimization_target": "copy resplit HBM artifacts to the S100P local cache and run residency/capacity probes against the resplit layout" if not errors else "repair missing or mismatched resplit HBM artifacts before runtime testing",
    "warnings": warnings,
    "errors": errors,
}
json_path = run_dir / "resplit_hbm_artifact_inventory_probe.json"
md_path = run_dir / "resplit_hbm_artifact_inventory_probe.md"
json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
lines = [
    "# Dream 7B Resplit HBM Artifact Inventory Probe",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- hbm_dir: {payload['hbm_dir']}",
    f"- expected_specs: {payload['expected_specs']}",
    f"- expected_hbm_count: {payload['expected_hbm_count']}",
    f"- existing_hbm_count: {payload['existing_hbm_count']}",
    f"- manifest_entry_count: {payload['manifest_entry_count']}",
    f"- manifest_verified_count: {payload['manifest_verified_count']}",
    f"- total_hbm_size_bytes: {payload['total_hbm_size_bytes']}",
    f"- total_hbm_size_gib: {payload['total_hbm_size_gib']}",
    f"- next_optimization_target: {payload['next_optimization_target']}",
    "",
    "## Inventory",
    "",
]
for item in inventory:
    lines.append(
        f"- {item['spec']}: exists={item['exists']}, size_bytes={item['size_bytes']}, "
        f"sha256_ok={item['sha256_ok']}, path={item['path']}"
    )
lines.extend(["", "## Errors", ""])
lines.extend(f"- {item}" for item in errors) if errors else lines.append("- none")
lines.extend(["", "## Warnings", ""])
lines.extend(f"- {item}" for item in warnings) if warnings else lines.append("- none")
md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(md_path)
if errors:
    raise SystemExit("; ".join(errors))
PY
