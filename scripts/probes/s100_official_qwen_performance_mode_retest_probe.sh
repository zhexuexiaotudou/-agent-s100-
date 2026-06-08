#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
qwen_runtime_probe="${S100_OFFICIAL_QWEN_PERF_RETEST_RUNTIME_PROBE:-/usr/local/bin/s100-official-qwen-runtime-probe}"
devmem_bin="${S100_OFFICIAL_QWEN_PERF_RETEST_DEVMEM_BIN:-/usr/bin/devmem}"
target_value="${S100_OFFICIAL_QWEN_PERF_RETEST_TARGET_VALUE:-0x99}"

case "$report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_root" >&2
    exit 2
    ;;
esac

case "$qwen_runtime_probe" in
  /usr/local/bin/s100-official-qwen-runtime-probe|/tmp/s100_official_qwen_runtime_probe.sh) ;;
  *)
    echo "Refusing runtime probe path outside approved commands: $qwen_runtime_probe" >&2
    exit 2
    ;;
esac

case "$devmem_bin" in
  /usr/bin/devmem|/bin/busybox|/usr/bin/busybox) ;;
  *)
    echo "Refusing devmem path outside approved commands: $devmem_bin" >&2
    exit 2
    ;;
esac

if [[ "$target_value" != "0x99" ]]; then
  echo "Refusing target value other than official set_performance_mode.sh value 0x99: $target_value" >&2
  exit 2
fi

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/s100_official_qwen_performance_mode_retest_$stamp"
mkdir -p "$run_dir"

python3 - \
  "$run_dir" \
  "$report_root" \
  "$qwen_runtime_probe" \
  "$devmem_bin" \
  "$target_value" <<'PY'
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

run_dir = Path(sys.argv[1])
report_root = Path(sys.argv[2])
qwen_runtime_probe = Path(sys.argv[3])
devmem_bin = Path(sys.argv[4])
target_value = sys.argv[5]
registers = ["0x2b047000", "0x2b047004"]
errors = []
warnings = []


def run(argv, timeout=120, use_sudo=False):
    command = list(argv)
    if use_sudo:
        command = ["sudo", "-n"] + command
    try:
        completed = subprocess.run(command, text=True, capture_output=True, timeout=timeout)
        return {
            "argv": command,
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "argv": command,
            "returncode": None,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
            "timed_out": True,
        }


def first_line(text):
    lines = (text or "").splitlines()
    return lines[0] if lines else ""


def read_reg(addr):
    return run([str(devmem_bin), addr, "32"], timeout=10, use_sudo=True)


def write_reg(addr):
    return run([str(devmem_bin), addr, "32", target_value], timeout=10, use_sudo=True)


def latest_qwen_runtime_report():
    paths = [path for path in report_root.glob("s100_official_qwen_runtime_*/official_qwen_runtime_probe.json") if path.is_file()]
    if not paths:
        return None, None
    path = max(paths, key=lambda item: item.stat().st_mtime)
    return path, json.loads(path.read_text(encoding="utf-8"))


def write_capture(name, result):
    path = run_dir / name
    path.write_text(
        "\n".join(
            [
                "$ " + " ".join(result.get("argv") or []),
                f"returncode: {result.get('returncode')}",
                f"timed_out: {result.get('timed_out')}",
                "",
                "## stdout",
                result.get("stdout") or "",
                "",
                "## stderr",
                result.get("stderr") or "",
                "",
            ]
        ),
        encoding="utf-8",
        errors="replace",
    )
    return str(path)


boardid = run(["hrut_boardid"], timeout=10)
boardid_value = first_line(boardid.get("stdout"))
if boardid_value[:4] != "0x64":
    errors.append(f"boardid does not match S100P prefix 0x64: {boardid_value}")
if not qwen_runtime_probe.is_file():
    errors.append(f"official Qwen runtime probe is missing: {qwen_runtime_probe}")
if not devmem_bin.is_file():
    errors.append(f"devmem binary is missing: {devmem_bin}")

before = {addr: read_reg(addr) for addr in registers} if not errors else {}
write_results = {}
after = {}
runtime_result = None
runtime_report_path = None
runtime_report = None
if not errors:
    for addr in registers:
        write_results[addr] = write_reg(addr)
        if write_results[addr].get("returncode") != 0:
            errors.append(f"failed to write performance register {addr}: {first_line(write_results[addr].get('stderr'))}")
    after = {addr: read_reg(addr) for addr in registers}
    if not errors:
        runtime_result = run([str(qwen_runtime_probe), str(report_root)], timeout=180)
        runtime_report_path, runtime_report = latest_qwen_runtime_report()

before_values = {addr: first_line(result.get("stdout")) for addr, result in before.items()}
after_values = {addr: first_line(result.get("stdout")) for addr, result in after.items()}
target_register_value = "0x00000099"
target_applied = bool(after_values) and all(value.lower() == target_register_value for value in after_values.values())
runtime_completed = runtime_report.get("runtime_completed") if runtime_report else None
memory_alloc_failure_observed = runtime_report.get("memory_alloc_failure_observed") if runtime_report else None

if after_values and not all(value.lower().endswith("99") for value in after_values.values()):
    warnings.append(f"performance registers after apply are not both {target_value}: {after_values}")
if runtime_report and memory_alloc_failure_observed:
    warnings.append("official Qwen still reports BPU/common-buffer memory allocation failure after performance-mode register apply")
if runtime_report and runtime_completed:
    warnings.append("official Qwen runtime completed after performance-mode register apply; collect utilization telemetry before using it as a baseline")

captures = {"boardid": write_capture("boardid.txt", boardid)}
for addr, result in before.items():
    captures[f"before_{addr}"] = write_capture(f"before_{addr}.txt", result)
for addr, result in write_results.items():
    captures[f"write_{addr}"] = write_capture(f"write_{addr}.txt", result)
for addr, result in after.items():
    captures[f"after_{addr}"] = write_capture(f"after_{addr}.txt", result)
if runtime_result:
    captures["qwen_runtime_probe"] = write_capture("qwen_runtime_probe.txt", runtime_result)

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_s100_official_qwen_performance_mode_retest_probe" if not errors else "failed_s100_official_qwen_performance_mode_retest_probe",
    "run_dir": str(run_dir),
    "report_root": str(report_root),
    "qwen_runtime_probe": str(qwen_runtime_probe),
    "devmem_bin": str(devmem_bin),
    "target_value": target_value,
    "boardid": boardid_value,
    "registers": registers,
    "before_values": before_values,
    "after_values": after_values,
    "target_applied": target_applied,
    "runtime_probe_returncode": runtime_result.get("returncode") if runtime_result else None,
    "runtime_probe_timed_out": runtime_result.get("timed_out") if runtime_result else None,
    "runtime_report_path": str(runtime_report_path) if runtime_report_path else "",
    "runtime_completed_after_performance_mode": runtime_completed,
    "memory_alloc_failure_observed_after_performance_mode": memory_alloc_failure_observed,
    "runtime_returncode_after_performance_mode": runtime_report.get("runtime_returncode") if runtime_report else None,
    "hbm_load_success_observed_after_performance_mode": runtime_report.get("hbm_load_success_observed") if runtime_report else None,
    "init_model_success_observed_after_performance_mode": runtime_report.get("init_model_success_observed") if runtime_report else None,
    "next_probe_target": "inspect ION/common-buffer reserved memory and HBMEM/UCP allocation prerequisites; performance-mode register apply alone did not clear official Qwen allocation failure" if memory_alloc_failure_observed else "collect hrt_ucp_monitor utilization telemetry for official Qwen after performance-mode apply",
    "captures": captures,
    "warnings": warnings,
    "errors": errors,
}

(run_dir / "performance_mode_retest_probe.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
warning_lines = [f"- {item}" for item in warnings] if warnings else ["- none"]
error_lines = [f"- {item}" for item in errors] if errors else ["- none"]
lines = [
    "# S100 Official Qwen Performance Mode Retest Probe",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- boardid: {payload['boardid']}",
    f"- devmem_bin: {payload['devmem_bin']}",
    f"- target_value: {payload['target_value']}",
    f"- before_values: {payload['before_values']}",
    f"- after_values: {payload['after_values']}",
    f"- target_applied: {payload['target_applied']}",
    f"- runtime_report_path: {payload['runtime_report_path']}",
    f"- runtime_completed_after_performance_mode: {payload['runtime_completed_after_performance_mode']}",
    f"- runtime_returncode_after_performance_mode: {payload['runtime_returncode_after_performance_mode']}",
    f"- memory_alloc_failure_observed_after_performance_mode: {payload['memory_alloc_failure_observed_after_performance_mode']}",
    f"- hbm_load_success_observed_after_performance_mode: {payload['hbm_load_success_observed_after_performance_mode']}",
    f"- init_model_success_observed_after_performance_mode: {payload['init_model_success_observed_after_performance_mode']}",
    f"- next_probe_target: {payload['next_probe_target']}",
    "",
    "## Captures",
    "",
]
lines.extend(f"- {key}: {value}" for key, value in captures.items())
lines.extend(["", "## Warnings", "", *warning_lines, "", "## Errors", "", *error_lines, ""])
(run_dir / "performance_mode_retest_probe.md").write_text("\n".join(lines), encoding="utf-8")
print(run_dir / "performance_mode_retest_probe.md")
if errors:
    raise SystemExit("; ".join(errors))
PY
