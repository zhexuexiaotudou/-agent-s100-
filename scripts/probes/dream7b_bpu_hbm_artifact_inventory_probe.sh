#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
forward_script="${DREAM7B_BPU_ARTIFACT_INVENTORY_FORWARD_SCRIPT:-/mnt/nas/openclaw/runtimes/dream7b-bpu-forward/dream7b_segmented_hbm_python_forward.py}"
nas_hbm_dir="${DREAM7B_BPU_ARTIFACT_INVENTORY_NAS_HBM_DIR:-/mnt/nas/openclaw/models/dream7b-hbm/segments6}"
nas_fine_hbm_dir="${DREAM7B_BPU_ARTIFACT_INVENTORY_NAS_FINE_HBM_DIR:-/mnt/nas/openclaw/models/dream7b-hbm/fine-seq16}"
local_hbm_dir="${DREAM7B_BPU_ARTIFACT_INVENTORY_LOCAL_HBM_DIR:-/home/sunrise/.cache/openclaw/dream7b-hbm/segments6}"
local_fine_hbm_dir="${DREAM7B_BPU_ARTIFACT_INVENTORY_LOCAL_FINE_HBM_DIR:-/home/sunrise/.cache/openclaw/dream7b-hbm/fine-seq16}"
verify_manifest="${DREAM7B_BPU_ARTIFACT_INVENTORY_VERIFY_MANIFEST:-1}"

case "$report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_root" >&2
    exit 2
    ;;
esac

case "$forward_script" in
  /mnt/nas/openclaw/runtimes/dream7b-bpu-forward/dream7b_segmented_hbm_python_forward.py|/root/.openclaw/workspace/*/dream7b_segmented_hbm_python_forward.py|/tmp/*/dream7b_segmented_hbm_python_forward.py) ;;
  *)
    echo "Refusing forward script outside approved Dream 7B runtime locations: $forward_script" >&2
    exit 2
    ;;
esac

for path in "$nas_hbm_dir" "$nas_fine_hbm_dir"; do
  case "$path" in
    /mnt/nas/openclaw/models/dream7b-hbm/segments6|/mnt/nas/openclaw/models/dream7b-hbm/fine-seq16|/root/.openclaw/workspace/models/dream7b-hbm/*|/tmp/dream7b-hbm/*) ;;
    *)
      echo "Refusing NAS HBM path outside approved Dream 7B HBM directories: $path" >&2
      exit 2
      ;;
  esac
done

for path in "$local_hbm_dir" "$local_fine_hbm_dir"; do
  case "$path" in
    /home/sunrise/.cache/openclaw/dream7b-hbm/segments6|/home/sunrise/.cache/openclaw/dream7b-hbm/fine-seq16|/tmp/dream7b-hbm-cache/*) ;;
    *)
      echo "Refusing local HBM cache path outside approved Dream 7B cache directories: $path" >&2
      exit 2
      ;;
  esac
done

case "$verify_manifest" in
  0|1) ;;
  *)
    echo "DREAM7B_BPU_ARTIFACT_INVENTORY_VERIFY_MANIFEST must be 0 or 1." >&2
    exit 2
    ;;
esac

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_hbm_artifact_inventory_$stamp"
mkdir -p "$run_dir"

python3 - \
  "$run_dir" \
  "$forward_script" \
  "$nas_hbm_dir" \
  "$nas_fine_hbm_dir" \
  "$local_hbm_dir" \
  "$local_fine_hbm_dir" \
  "$verify_manifest" <<'PY'
import ast
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

run_dir = Path(sys.argv[1])
forward_script = Path(sys.argv[2])
nas_hbm_dir = Path(sys.argv[3])
nas_fine_hbm_dir = Path(sys.argv[4])
local_hbm_dir = Path(sys.argv[5])
local_fine_hbm_dir = Path(sys.argv[6])
verify_manifest = sys.argv[7] == "1"
errors = []
warnings = []


def load_segment_constant(script_path, name):
    tree = ast.parse(script_path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise ValueError(f"missing constant {name} in {script_path}")


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def manifest_entries(manifest_path):
    entries = {}
    if not manifest_path.is_file():
        return entries
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) >= 2:
            entries[parts[1]] = parts[0]
    return entries


if not forward_script.is_file():
    errors.append(f"missing forward_script: {forward_script}")
    seg6 = []
    fine = []
else:
    try:
        seg6 = load_segment_constant(forward_script, "SEGMENTS6")
        fine = load_segment_constant(forward_script, "FINE_ADJACENT_SEGMENTS")
    except Exception as exc:
        errors.append(f"failed to parse forward script segment constants: {exc}")
        seg6 = []
        fine = []

expected = {}
for segment, source, rel_file, model_name, input_kind in seg6:
    expected[("base", rel_file)] = {
        "segment": segment,
        "source": source,
        "relative_file": rel_file,
        "model_name": model_name,
        "input_kind": input_kind,
        "plans": ["SEGMENTS6"],
    }
for segment, source, rel_file, model_name, input_kind in fine:
    key = (source, rel_file)
    row = expected.setdefault(
        key,
        {
            "segment": segment,
            "source": source,
            "relative_file": rel_file,
            "model_name": model_name,
            "input_kind": input_kind,
            "plans": [],
        },
    )
    if "FINE_ADJACENT_SEGMENTS" not in row["plans"]:
        row["plans"].append("FINE_ADJACENT_SEGMENTS")

entries = sorted(expected.values(), key=lambda item: (item["source"], item["relative_file"]))
manifest_by_root = {
    "nas": manifest_entries(nas_hbm_dir / "manifest.sha256"),
    "local": manifest_entries(local_hbm_dir / "manifest.sha256"),
}
inventory = []
size_pairs = []
manifest_verified_count = 0
manifest_expected_count = 0

for item in entries:
    source = item["source"]
    relative_file = item["relative_file"]
    nas_root = nas_hbm_dir if source == "base" else nas_fine_hbm_dir
    local_root = local_hbm_dir if source == "base" else local_fine_hbm_dir
    paths = {
        "nas": nas_root / relative_file,
        "local": local_root / relative_file,
    }
    sizes = {}
    exists = {}
    manifest_status = {}
    for root_name, path in paths.items():
        exists[root_name] = path.is_file()
        if exists[root_name]:
            sizes[root_name] = path.stat().st_size
        else:
            sizes[root_name] = None
            errors.append(f"missing {root_name} artifact: {path}")
        if source == "base":
            expected_sha = manifest_by_root[root_name].get(relative_file)
            if expected_sha:
                manifest_expected_count += 1
                if verify_manifest and exists[root_name]:
                    actual_sha = sha256_file(path)
                    ok = actual_sha == expected_sha
                    manifest_status[root_name] = {
                        "expected_sha256": expected_sha,
                        "actual_sha256": actual_sha,
                        "ok": ok,
                    }
                    if ok:
                        manifest_verified_count += 1
                    else:
                        errors.append(f"{root_name} manifest sha256 mismatch for {path}")
                else:
                    manifest_status[root_name] = {
                        "expected_sha256": expected_sha,
                        "actual_sha256": None,
                        "ok": None,
                    }
            else:
                manifest_status[root_name] = {
                    "expected_sha256": None,
                    "actual_sha256": None,
                    "ok": False,
                }
                errors.append(f"{root_name} manifest missing entry for {relative_file}")
    size_match = exists["nas"] and exists["local"] and sizes["nas"] == sizes["local"]
    if exists["nas"] and exists["local"]:
        size_pairs.append(size_match)
        if not size_match:
            errors.append(f"NAS/local size mismatch for {relative_file}: {sizes}")
    inventory.append(
        {
            **item,
            "nas_path": str(paths["nas"]),
            "local_path": str(paths["local"]),
            "nas_exists": exists["nas"],
            "local_exists": exists["local"],
            "nas_bytes": sizes["nas"],
            "local_bytes": sizes["local"],
            "size_match": bool(size_match),
            "manifest_status": manifest_status,
        }
    )

expected_base_count = sum(1 for item in entries if item["source"] == "base")
expected_fine_count = sum(1 for item in entries if item["source"] == "fine")
nas_existing_count = sum(1 for item in inventory if item["nas_exists"])
local_existing_count = sum(1 for item in inventory if item["local_exists"])
size_match_count = sum(1 for item in inventory if item["size_match"])
expected_artifact_count = len(entries)
required_manifest_expected_count = expected_base_count * 2

if expected_base_count != 6:
    errors.append(f"unexpected expected_base_count: {expected_base_count}")
if expected_fine_count != 8:
    errors.append(f"unexpected expected_fine_count: {expected_fine_count}")
if nas_existing_count != expected_artifact_count:
    errors.append(f"unexpected nas_existing_count: {nas_existing_count}")
if local_existing_count != expected_artifact_count:
    errors.append(f"unexpected local_existing_count: {local_existing_count}")
if size_match_count != expected_artifact_count:
    errors.append(f"unexpected size_match_count: {size_match_count}")
if verify_manifest and manifest_verified_count != required_manifest_expected_count:
    errors.append(f"unexpected manifest_verified_count: {manifest_verified_count}")

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_bpu_hbm_artifact_inventory_probe" if not errors else "failed_dream7b_bpu_hbm_artifact_inventory_probe",
    "forward_script": str(forward_script),
    "nas_hbm_dir": str(nas_hbm_dir),
    "nas_fine_hbm_dir": str(nas_fine_hbm_dir),
    "local_hbm_dir": str(local_hbm_dir),
    "local_fine_hbm_dir": str(local_fine_hbm_dir),
    "verify_manifest": verify_manifest,
    "expected_artifact_count": expected_artifact_count,
    "expected_base_count": expected_base_count,
    "expected_fine_count": expected_fine_count,
    "nas_existing_count": nas_existing_count,
    "local_existing_count": local_existing_count,
    "size_match_count": size_match_count,
    "manifest_expected_count": manifest_expected_count,
    "manifest_verified_count": manifest_verified_count,
    "required_manifest_expected_count": required_manifest_expected_count,
    "inventory": inventory,
    "warnings": warnings,
    "errors": errors,
}
(run_dir / "hbm_artifact_inventory_probe.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
inventory_lines = [
    f"| {item['source']} | {item['relative_file']} | {item['nas_exists']} | {item['local_exists']} | {item['nas_bytes']} | {item['local_bytes']} | {item['size_match']} | {','.join(item['plans'])} |"
    for item in inventory
]
warning_lines = [f"- {item}" for item in warnings] if warnings else ["- none"]
error_lines = [f"- {item}" for item in errors] if errors else ["- none"]
(run_dir / "hbm_artifact_inventory_probe.md").write_text(
    "\n".join([
        "# Dream 7B BPU HBM Artifact Inventory Probe",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- verdict: {payload['verdict']}",
        f"- forward_script: {payload['forward_script']}",
        f"- nas_hbm_dir: {payload['nas_hbm_dir']}",
        f"- nas_fine_hbm_dir: {payload['nas_fine_hbm_dir']}",
        f"- local_hbm_dir: {payload['local_hbm_dir']}",
        f"- local_fine_hbm_dir: {payload['local_fine_hbm_dir']}",
        f"- expected_artifact_count: {payload['expected_artifact_count']}",
        f"- expected_base_count: {payload['expected_base_count']}",
        f"- expected_fine_count: {payload['expected_fine_count']}",
        f"- nas_existing_count: {payload['nas_existing_count']}",
        f"- local_existing_count: {payload['local_existing_count']}",
        f"- size_match_count: {payload['size_match_count']}",
        f"- manifest_expected_count: {payload['manifest_expected_count']}",
        f"- manifest_verified_count: {payload['manifest_verified_count']}",
        "",
        "## Inventory",
        "",
        "| source | relative_file | nas_exists | local_exists | nas_bytes | local_bytes | size_match | plans |",
        "| --- | --- | --- | --- | ---: | ---: | --- | --- |",
        *inventory_lines,
        "",
        "## Warnings",
        "",
        *warning_lines,
        "",
        "## Errors",
        "",
        *error_lines,
        "",
    ]) + "\n",
    encoding="utf-8",
)
print(run_dir / "hbm_artifact_inventory_probe.md")
if errors:
    raise SystemExit("; ".join(errors))
PY
