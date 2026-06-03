#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
prompt="${2:-Explain why BPU matters.}"

cpu_timeout="${DREAM7B_CPU_QUALITY_TIMEOUT:-180}"
cpu_steps="${DREAM7B_CPU_QUALITY_STEPS:-4}"
cpu_max_tokens="${DREAM7B_CPU_QUALITY_MAX_TOKENS:-8}"
bpu_timeout="${DREAM7B_BPU_QUALITY_TIMEOUT:-900}"
bpu_steps="${DREAM7B_BPU_QUALITY_STEPS:-2}"
bpu_remasking="${DREAM7B_BPU_QUALITY_REMASKING:-entropy_exit}"
bpu_forward_cmd="${DREAM7B_BPU_QUALITY_FORWARD_CMD:-}"

case "$report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_root" >&2
    exit 2
    ;;
esac

if ! command -v dream7b-text >/dev/null 2>&1; then
  echo "Missing deployed CPU Dream command: dream7b-text" >&2
  exit 4
fi

if ! command -v dream7b-bpu-diffusion-loop-probe >/dev/null 2>&1; then
  echo "Missing deployed BPU Dream command: dream7b-bpu-diffusion-loop-probe" >&2
  exit 4
fi

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_cpu_quality_gate_$stamp"
mkdir -p "$run_dir"

cpu_stdout="$run_dir/cpu.stdout"
cpu_stderr="$run_dir/cpu.stderr"
bpu_stdout="$run_dir/bpu.stdout"
bpu_stderr="$run_dir/bpu.stderr"
summary_json="$run_dir/summary.json"
summary_md="$run_dir/summary.md"

set +e
DREAM7B_MAX_TOKENS="$cpu_max_tokens" \
DREAM7B_STEPS="$cpu_steps" \
timeout "$cpu_timeout" dream7b-text "$prompt" > "$cpu_stdout" 2> "$cpu_stderr"
cpu_rc=$?

DREAM7B_BPU_DIFFUSION_STEPS="$bpu_steps" \
DREAM7B_BPU_REMASKING="$bpu_remasking" \
DREAM7B_BPU_FORWARD_CMD="${bpu_forward_cmd:-dream7b-bpu-forward}" \
timeout "$bpu_timeout" dream7b-bpu-diffusion-loop-probe "$report_root" "$prompt" > "$bpu_stdout" 2> "$bpu_stderr"
bpu_rc=$?
set -e

python3 - "$prompt" "$cpu_rc" "$bpu_rc" "$cpu_steps" "$cpu_max_tokens" "$bpu_steps" "$bpu_remasking" "${bpu_forward_cmd:-dream7b-bpu-forward}" "$cpu_stdout" "$cpu_stderr" "$bpu_stdout" "$bpu_stderr" "$summary_json" "$summary_md" <<'PY'
import json
import re
import sys
from datetime import datetime
from pathlib import Path

(
    prompt,
    cpu_rc_text,
    bpu_rc_text,
    cpu_steps_text,
    cpu_max_tokens_text,
    bpu_steps_text,
    bpu_remasking,
    bpu_forward_cmd,
    cpu_stdout,
    cpu_stderr,
    bpu_stdout,
    bpu_stderr,
    summary_json,
    summary_md,
) = sys.argv[1:15]

cpu_stdout_path = Path(cpu_stdout)
cpu_stderr_path = Path(cpu_stderr)
bpu_stdout_path = Path(bpu_stdout)
bpu_stderr_path = Path(bpu_stderr)
cpu_text = cpu_stdout_path.read_text(encoding="utf-8", errors="replace").strip()
cpu_err = cpu_stderr_path.read_text(encoding="utf-8", errors="replace").strip()
bpu_out = bpu_stdout_path.read_text(encoding="utf-8", errors="replace")
bpu_err = bpu_stderr_path.read_text(encoding="utf-8", errors="replace").strip()

bpu_summary_md = None
for line in bpu_out.splitlines():
    line = line.strip()
    if line.endswith("/summary.md") and "dream7b_bpu_diffusion_loop_" in line:
        bpu_summary_md = Path(line)
        break

bpu_payload = {}
if bpu_summary_md and bpu_summary_md.exists():
    bpu_summary_json = bpu_summary_md.with_name("summary.json")
    if bpu_summary_json.exists():
        bpu_payload = json.loads(bpu_summary_json.read_text(encoding="utf-8"))
else:
    bpu_summary_json = None

bpu_text = str(bpu_payload.get("decoded_final", "")).strip()
cpu_norm = re.sub(r"\s+", " ", cpu_text).strip()
bpu_norm = re.sub(r"\s+", " ", bpu_text).strip()
both_ran = int(cpu_rc_text) == 0 and int(bpu_rc_text) == 0 and bool(bpu_payload)
exact_match = both_ran and cpu_norm == bpu_norm

if both_ran:
    verdict = "ok_dream7b_bpu_cpu_quality_gate_recorded"
    quality_status = "exact_match" if exact_match else "diverged_expected_for_seq16_probe"
else:
    verdict = "blocked_dream7b_bpu_cpu_quality_gate"
    quality_status = "missing_cpu_or_bpu_output"

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": verdict,
    "quality_status": quality_status,
    "prompt": prompt,
    "cpu": {
        "command": "dream7b-text",
        "returncode": int(cpu_rc_text),
        "steps": int(cpu_steps_text),
        "max_tokens": int(cpu_max_tokens_text),
        "stdout": cpu_text,
        "stderr_preview": cpu_err[:1000],
    },
    "bpu": {
        "command": "dream7b-bpu-diffusion-loop-probe",
        "forward_command": bpu_forward_cmd,
        "returncode": int(bpu_rc_text),
        "steps": int(bpu_steps_text),
        "remasking": bpu_remasking,
        "summary_md": str(bpu_summary_md) if bpu_summary_md else "",
        "summary_json": str(bpu_summary_json) if bpu_summary_md else "",
        "decoded_final": bpu_text,
        "verdict": bpu_payload.get("verdict", ""),
        "remaining_mask_positions": bpu_payload.get("remaining_mask_positions", []),
        "stderr_preview": bpu_err[:1000],
    },
    "comparison": {
        "exact_match": exact_match,
        "cpu_normalized": cpu_norm,
        "bpu_normalized": bpu_norm,
        "cpu_char_count": len(cpu_norm),
        "bpu_char_count": len(bpu_norm),
    },
    "notes": [
        "This is a quality coverage gate, not an acceptance threshold.",
        "Divergence is expected while the BPU path uses seq16 segmented probes and a bounded host-side loop.",
        "Use this report to define future acceptable divergence once production prompt length and sampling policy are fixed.",
    ],
}
Path(summary_json).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

lines = [
    "# Dream 7B BPU vs CPU Quality Gate",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {verdict}",
    f"- quality_status: {quality_status}",
    f"- bpu_forward_command: {bpu_forward_cmd}",
    f"- prompt: {prompt}",
    "",
    "## CPU Output",
    "",
    "```text",
    cpu_text or "none",
    "```",
    "",
    "## BPU Output",
    "",
    "```text",
    bpu_text or "none",
    "```",
    "",
    "## Comparison",
    "",
    f"- exact_match: {exact_match}",
    f"- cpu_char_count: {len(cpu_norm)}",
    f"- bpu_char_count: {len(bpu_norm)}",
    f"- bpu_summary: {payload['bpu']['summary_md']}",
    "",
    "## Boundary",
    "",
    "- This records CPU/BPU divergence for follow-up thresholds.",
    "- It does not fail the BPU deployment path solely because seq16 probe output differs from CPU Dream text.",
]
Path(summary_md).write_text("\n".join(lines) + "\n", encoding="utf-8")
print(summary_md)
PY
