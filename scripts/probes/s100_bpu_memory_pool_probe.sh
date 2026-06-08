#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
sdk_root="${S100_BPU_MEMORY_POOL_SDK_ROOT:-/mnt/nas/openclaw/toolchains/s100_llm_sdk/D-Robotics_LLM_S100_1.0.0_SDK}"
related_report_root="${S100_BPU_MEMORY_POOL_RELATED_REPORT_ROOT:-/mnt/nas/openclaw/reports/models}"

case "$report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_root" >&2
    exit 2
    ;;
esac

case "$sdk_root" in
  /mnt/nas/openclaw/toolchains/s100_llm_sdk/D-Robotics_LLM_S100_1.0.0_SDK|/mnt/nas/openclaw/toolchains/s100_llm_sdk/D-Robotics_LLM_S100_1.0.0_SDK/|/opt/D-Robotics_LLM_S100_1.0.0_SDK|/opt/D-Robotics_LLM_S100_1.0.0_SDK/) ;;
  *)
    echo "Refusing SDK path outside approved S100 official LLM SDK directories: $sdk_root" >&2
    exit 2
    ;;
esac

case "$related_report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing related report path outside approved report directories: $related_report_root" >&2
    exit 2
    ;;
esac

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/s100_bpu_memory_pool_$stamp"
mkdir -p "$run_dir"

python3 - \
  "$run_dir" \
  "$sdk_root" \
  "$related_report_root" <<'PY'
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

run_dir = Path(sys.argv[1])
sdk_root = Path(sys.argv[2])
related_report_root = Path(sys.argv[3])
runtime_root = sdk_root / "oellm_runtime"
performance_mode_script = runtime_root / "set_performance_mode.sh"
errors = []
warnings = []


def run(argv, timeout=20, use_sudo=False, env=None):
    command = list(argv)
    if use_sudo:
        command = ["sudo", "-n"] + command
    merged_env = dict(os.environ)
    if env:
        merged_env.update(env)
    try:
        completed = subprocess.run(command, text=True, capture_output=True, timeout=timeout, env=merged_env)
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
    except FileNotFoundError as exc:
        return {
            "argv": command,
            "returncode": None,
            "stdout": "",
            "stderr": str(exc),
            "timed_out": False,
        }


def latest_json(pattern):
    paths = [path for path in related_report_root.glob(pattern) if path.is_file()]
    if not paths:
        return None, None
    path = max(paths, key=lambda item: item.stat().st_mtime)
    return path, json.loads(path.read_text(encoding="utf-8"))


def first_line(text):
    return (text or "").splitlines()[0] if (text or "").splitlines() else ""


def command_path_line(text, basename):
    for line in (text or "").splitlines():
        stripped = line.strip()
        if stripped.endswith("/" + basename) or stripped == basename:
            return stripped
    return first_line(text)


def write_capture(name, result):
    path = run_dir / name
    payload = [
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
    path.write_text("\n".join(payload), encoding="utf-8", errors="replace")
    return str(path)


def read_root_text(path, timeout=10):
    result = run(["cat", str(path)], timeout=timeout, use_sudo=True)
    return result


def write_text_capture(name, path, result):
    capture_path = run_dir / name
    payload = [
        f"path: {path}",
        "$ " + " ".join(result.get("argv") or []),
        f"returncode: {result.get('returncode')}",
        f"timed_out: {result.get('timed_out')}",
        "",
        result.get("stdout") or "",
        "",
        "## stderr",
        result.get("stderr") or "",
        "",
    ]
    capture_path.write_text("\n".join(payload), encoding="utf-8", errors="replace")
    return str(capture_path)


def parse_heap_debug_text(text):
    total_size = None
    allocated_total = None
    allocations = []
    for line in (text or "").splitlines():
        total_match = re.search(r"heap total size\s+(\d+)", line)
        if total_match:
            total_size = int(total_match.group(1))
            continue
        allocated_match = re.match(r"^\s*total\s+(\d+)\s*$", line)
        if allocated_match:
            allocated_total = int(allocated_match.group(1))
            continue
        allocation_match = re.match(r"^\s*(\S+)\s+(\d+)\s+(\d+)\s+(\S+)\s+(\d+)\s+.*\s+([0-9A-Fa-f]+)\s*$", line)
        if allocation_match:
            allocations.append({
                "client": allocation_match.group(1),
                "pid": int(allocation_match.group(2)),
                "tgid": int(allocation_match.group(3)),
                "type": allocation_match.group(4),
                "size": int(allocation_match.group(5)),
                "paddr": "0x" + allocation_match.group(6),
            })
    return {
        "total_size": total_size,
        "allocated_total": allocated_total,
        "available_estimate": (total_size - allocated_total) if total_size is not None and allocated_total is not None else None,
        "allocations": allocations,
    }


def parse_iovmm_text(text):
    total_mappings = None
    total_unmappings = None
    sid = None
    for line in (text or "").splitlines():
        sid_match = re.search(r"\bsid\s+(\S+)", line)
        if sid_match:
            sid = sid_match.group(1)
        mappings_match = re.search(r"Total(?: number of)? mappings\s*:\s+(\d+)", line)
        if mappings_match:
            total_mappings = int(mappings_match.group(1))
        unmap_match = re.search(r"Total(?: number of)? unmappings\s*:\s+(\d+)", line)
        if unmap_match:
            total_unmappings = int(unmap_match.group(1))
    return {
        "sid": sid,
        "total_mappings": total_mappings,
        "total_unmappings": total_unmappings,
        "has_current_region_rows": bool(re.search(r"^\s*0x[0-9A-Fa-f]+", text or "", re.MULTILINE)),
    }


def parse_dt_string(path):
    result = read_root_text(path)
    if result.get("returncode") != 0:
        return ""
    return (result.get("stdout") or "").replace("\x00", " ").strip()


def parse_dt_reg(path):
    result = run(["od", "-An", "-tx1", "-v", str(path)], timeout=10, use_sudo=True)
    if result.get("returncode") != 0:
        return None
    hex_bytes = re.findall(r"\b[0-9a-fA-F]{2}\b", result.get("stdout") or "")
    raw = bytes(int(item, 16) for item in hex_bytes)
    if len(raw) < 16:
        return None
    cells = [int.from_bytes(raw[index:index + 4], "big") for index in range(0, 16, 4)]
    base = (cells[0] << 32) | cells[1]
    size = (cells[2] << 32) | cells[3]
    return {
        "base": base,
        "base_hex": f"0x{base:016X}",
        "size": size,
        "size_hex": f"0x{size:016X}",
        "size_mib": round(size / 1048576, 3),
    }


boardid = run(["hrut_boardid"], timeout=10)
cmdline = Path("/proc/cmdline").read_text(encoding="utf-8", errors="replace") if Path("/proc/cmdline").is_file() else ""
meminfo = Path("/proc/meminfo").read_text(encoding="utf-8", errors="replace") if Path("/proc/meminfo").is_file() else ""
modules = Path("/proc/modules").read_text(encoding="utf-8", errors="replace") if Path("/proc/modules").is_file() else ""
mounts = Path("/proc/mounts").read_text(encoding="utf-8", errors="replace") if Path("/proc/mounts").is_file() else ""

which_devmem = run(["sh", "-lc", "command -v devmem || true"], timeout=10)
sudo_which_devmem = run(["sh", "-lc", "command -v devmem || true"], timeout=10, use_sudo=True)
usr_hobot_devmem = Path("/usr/hobot/bin/devmem")
usr_bin_devmem = Path("/usr/bin/devmem")
busybox_devmem = run(["/usr/bin/busybox", "--list"], timeout=10)
busybox_has_devmem = "devmem" in set((busybox_devmem.get("stdout") or "").splitlines())
devmem_default_test = run(["devmem", "0x2b047000", "32"], timeout=10, use_sudo=True)
devmem_busybox_test = run(["/usr/bin/devmem", "0x2b047000", "32"], timeout=10, use_sudo=True)
perf_reg_0 = run(["/usr/bin/devmem", "0x2b047000", "32"], timeout=10, use_sudo=True)
perf_reg_1 = run(["/usr/bin/devmem", "0x2b047004", "32"], timeout=10, use_sudo=True)

ion_meminfo_cmd = "/usr/hobot/bin/ion_meminfo" if Path("/usr/hobot/bin/ion_meminfo").is_file() else "ion_meminfo"
memstat_cmd = "/usr/hobot/bin/memstat" if Path("/usr/hobot/bin/memstat").is_file() else "memstat"
ion_meminfo = run([ion_meminfo_cmd], timeout=20)
memstat = run([memstat_cmd], timeout=20)
ion_meminfo_fallback = run(["/bin/bash", "/usr/hobot/bin/ion_meminfo"], timeout=20) if Path("/usr/hobot/bin/ion_meminfo").is_file() and Path("/bin/bash").is_file() else None
memstat_fallback = run(["/bin/busybox", "ash", "/usr/hobot/bin/memstat"], timeout=20) if Path("/usr/hobot/bin/memstat").is_file() and Path("/bin/busybox").is_file() else None
ion_meminfo_shebang = first_line(Path("/usr/hobot/bin/ion_meminfo").read_text(encoding="utf-8", errors="replace")) if Path("/usr/hobot/bin/ion_meminfo").is_file() else ""
memstat_shebang = first_line(Path("/usr/hobot/bin/memstat").read_text(encoding="utf-8", errors="replace")) if Path("/usr/hobot/bin/memstat").is_file() else ""
ion_meminfo_shebang_interpreter_exists = Path(ion_meminfo_shebang[2:]).exists() if ion_meminfo_shebang.startswith("#!") else None
memstat_shebang_interpreter_exists = Path(memstat_shebang[2:]).exists() if memstat_shebang.startswith("#!") else None
debug_mount_present = any("/sys/kernel/debug" in line and "debugfs" in line for line in mounts.splitlines())
debug_probe = run(["sh", "-lc", "test -d /sys/kernel/debug && ls -ld /sys/kernel/debug && timeout 5 find /sys/kernel/debug -maxdepth 2 -type f -o -type d | sed -n '1,120p'"], timeout=10, use_sudo=True)
ion_debug_test = run(["test", "-d", "/sys/kernel/debug/ion"], timeout=10, use_sudo=True)

ion_heap_names = ["all_heap_info", "cma_reserved", "ion_cma", "carveout", "chunk", "system", "system_contig"]
ion_heap_results = {}
ion_heap_parsed = {}
ion_heap_captures = {}
for heap_name in ion_heap_names:
    heap_path = Path("/sys/kernel/debug/ion/heaps") / heap_name
    result = read_root_text(heap_path)
    ion_heap_results[heap_name] = result
    ion_heap_captures[heap_name] = write_text_capture(f"ion_heap_{heap_name}.txt", heap_path, result)
    if result.get("returncode") == 0:
        ion_heap_parsed[heap_name] = parse_heap_debug_text(result.get("stdout") or "")
    else:
        ion_heap_parsed[heap_name] = {
            "total_size": None,
            "allocated_total": None,
            "available_estimate": None,
            "allocations": [],
        }

ion_client_bpu0_path = Path("/sys/kernel/debug/ion/clients/bpu-0")
ion_client_bpu0 = read_root_text(ion_client_bpu0_path)
ion_client_bpu0_capture = write_text_capture("ion_client_bpu_0.txt", ion_client_bpu0_path, ion_client_bpu0)

iovmm_paths = {
    "bpu": Path("/sys/kernel/debug/iovmm/28108000.bpu"),
    "bpu_hp": Path("/sys/kernel/debug/iovmm/28100000.bpu_hp"),
}
iovmm_results = {}
iovmm_parsed = {}
iovmm_captures = {}
for name, path in iovmm_paths.items():
    result = read_root_text(path)
    iovmm_results[name] = result
    iovmm_captures[name] = write_text_capture(f"iovmm_{name}.txt", path, result)
    iovmm_parsed[name] = parse_iovmm_text(result.get("stdout") or "") if result.get("returncode") == 0 else {
        "sid": None,
        "total_mappings": None,
        "total_unmappings": None,
        "has_current_region_rows": False,
    }

reserved_memory_root = Path("/sys/firmware/devicetree/base/reserved-memory")
reserved_memory_entries = []
reserved_memory_summary = {}
reserved_memory_root_test = run(["test", "-d", str(reserved_memory_root)], timeout=10, use_sudo=True)
if reserved_memory_root_test.get("returncode") == 0:
    list_reserved = run(["find", str(reserved_memory_root), "-mindepth", "1", "-maxdepth", "1", "-type", "d", "-printf", "%f\n"], timeout=10, use_sudo=True)
    for node_name in sorted((list_reserved.get("stdout") or "").splitlines()):
        node_path = reserved_memory_root / node_name
        entry = {
            "name": node_name,
            "compatible": parse_dt_string(node_path / "compatible"),
            "reg": parse_dt_reg(node_path / "reg"),
        }
        reserved_memory_entries.append(entry)
        for key in ["ion_carveout", "ion_cma", "ion_reserved", "bpu_region", "vpu_ddr_reserved"]:
            if node_name.startswith(key):
                reserved_memory_summary[node_name] = entry
(run_dir / "reserved_memory_nodes.json").write_text(json.dumps(reserved_memory_entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

qwen_path, qwen_runtime = latest_json("s100_official_qwen_runtime_*/official_qwen_runtime_probe.json")
perf_retest_path, perf_retest = latest_json("s100_official_qwen_performance_mode_retest_*/performance_mode_retest_probe.json")
dream_util_path, dream_util = latest_json("dream7b_bpu_utilization_gap_*/utilization_gap_probe.json")
dream_window3_path, dream_window3 = latest_json("dream7b_bpu_window3_forward_feasibility_*/window3_forward_feasibility_probe.json")

boardid_value = first_line(boardid.get("stdout"))
official_script_would_match_s100p = boardid_value[:4] == "0x64"
default_devmem_path = command_path_line(which_devmem.get("stdout"), "devmem")
sudo_devmem_path = command_path_line(sudo_which_devmem.get("stdout"), "devmem")
default_devmem_broken = devmem_default_test.get("returncode") not in (0, None)
busybox_devmem_works = devmem_busybox_test.get("returncode") == 0

if official_script_would_match_s100p and default_devmem_broken and busybox_devmem_works:
    warnings.append("official performance-mode script may fail under sudo PATH because devmem resolves to a broken wrapper unless /usr/bin/devmem is selected")
if qwen_runtime and qwen_runtime.get("memory_alloc_failure_observed"):
    warnings.append("latest official Qwen runtime report still shows BPU/common-buffer memory allocation failure")
if perf_retest and perf_retest.get("memory_alloc_failure_observed_after_performance_mode"):
    warnings.append("latest official Qwen performance-mode retest still shows BPU/common-buffer memory allocation failure")
if dream_util and dream_util.get("diagnosis") == "hbm_reload_dominated":
    warnings.append("latest Dream utilization gap report remains hbm_reload_dominated")
if ion_meminfo_shebang and not ion_meminfo_shebang_interpreter_exists:
    warnings.append(f"ion_meminfo shebang interpreter is missing: {ion_meminfo_shebang}")
if memstat_shebang and not memstat_shebang_interpreter_exists:
    warnings.append(f"memstat shebang interpreter is missing: {memstat_shebang}")
if ion_heap_results.get("all_heap_info", {}).get("returncode") == 0 and ion_meminfo_fallback and ion_meminfo_fallback.get("returncode") != 0:
    warnings.append("direct debugfs read found /sys/kernel/debug/ion/heaps/all_heap_info even though ion_meminfo fallback reported an error")
if ion_heap_parsed.get("system", {}).get("total_size") == 0:
    warnings.append("ION system heap total size is zero")
if ion_heap_parsed.get("system_contig", {}).get("total_size") == 0:
    warnings.append("ION system_contig heap total size is zero")

captures = {
    "boardid": write_capture("boardid.txt", boardid),
    "which_devmem": write_capture("which_devmem.txt", which_devmem),
    "sudo_which_devmem": write_capture("sudo_which_devmem.txt", sudo_which_devmem),
    "devmem_default_test": write_capture("devmem_default_test.txt", devmem_default_test),
    "devmem_busybox_test": write_capture("devmem_busybox_test.txt", devmem_busybox_test),
    "ion_meminfo": write_capture("ion_meminfo.txt", ion_meminfo),
    "memstat": write_capture("memstat.txt", memstat),
    "debug_probe": write_capture("debug_probe.txt", debug_probe),
    "ion_client_bpu_0": ion_client_bpu0_capture,
    "reserved_memory_nodes": str(run_dir / "reserved_memory_nodes.json"),
}
captures.update({f"ion_heap_{name}": path for name, path in ion_heap_captures.items()})
captures.update({f"iovmm_{name}": path for name, path in iovmm_captures.items()})
if ion_meminfo_fallback:
    captures["ion_meminfo_fallback_bash"] = write_capture("ion_meminfo_fallback_bash.txt", ion_meminfo_fallback)
if memstat_fallback:
    captures["memstat_fallback_busybox_ash"] = write_capture("memstat_fallback_busybox_ash.txt", memstat_fallback)
(run_dir / "proc_cmdline.txt").write_text(cmdline, encoding="utf-8", errors="replace")
(run_dir / "proc_meminfo.txt").write_text(meminfo, encoding="utf-8", errors="replace")
(run_dir / "proc_modules.txt").write_text(modules, encoding="utf-8", errors="replace")
(run_dir / "proc_mounts.txt").write_text(mounts, encoding="utf-8", errors="replace")

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_s100_bpu_memory_pool_probe" if not errors else "failed_s100_bpu_memory_pool_probe",
    "run_dir": str(run_dir),
    "sdk_root": str(sdk_root),
    "performance_mode_script": str(performance_mode_script),
    "performance_mode_script_exists": performance_mode_script.is_file(),
    "performance_mode_script_action": "inspected_not_applied",
    "boardid": boardid_value,
    "official_script_would_match_s100p": official_script_would_match_s100p,
    "cmdline_contains_cma": "cma=" in cmdline,
    "cmdline_contains_ion": "ion" in cmdline.lower(),
    "debug_mount_present": debug_mount_present,
    "ion_debug_present": ion_debug_test.get("returncode") == 0,
    "ion_all_heap_info_exists": ion_heap_results.get("all_heap_info", {}).get("returncode") == 0,
    "ion_heap_names": sorted(ion_heap_parsed.keys()),
    "ion_heap_total_sizes": {key: value.get("total_size") for key, value in ion_heap_parsed.items()},
    "ion_heap_allocated_totals": {key: value.get("allocated_total") for key, value in ion_heap_parsed.items()},
    "ion_heap_available_estimates": {key: value.get("available_estimate") for key, value in ion_heap_parsed.items()},
    "ion_heap_bpu_allocation_counts": {
        key: sum(1 for allocation in value.get("allocations", []) if allocation.get("client", "").startswith("bpu") or allocation.get("type", "").startswith("bpu"))
        for key, value in ion_heap_parsed.items()
    },
    "ion_heap_bpu_allocation_sizes": {
        key: sum(allocation.get("size", 0) for allocation in value.get("allocations", []) if allocation.get("client", "").startswith("bpu") or allocation.get("type", "").startswith("bpu"))
        for key, value in ion_heap_parsed.items()
    },
    "system_heap_total_size": ion_heap_parsed.get("system", {}).get("total_size"),
    "system_contig_heap_total_size": ion_heap_parsed.get("system_contig", {}).get("total_size"),
    "carveout_heap_total_size": ion_heap_parsed.get("carveout", {}).get("total_size"),
    "carveout_heap_allocated_total": ion_heap_parsed.get("carveout", {}).get("allocated_total"),
    "cma_reserved_heap_total_size": ion_heap_parsed.get("cma_reserved", {}).get("total_size"),
    "cma_reserved_heap_allocated_total": ion_heap_parsed.get("cma_reserved", {}).get("allocated_total"),
    "ion_cma_heap_total_size": ion_heap_parsed.get("ion_cma", {}).get("total_size"),
    "ion_cma_heap_allocated_total": ion_heap_parsed.get("ion_cma", {}).get("allocated_total"),
    "ion_client_bpu_0_exists": ion_client_bpu0.get("returncode") == 0,
    "ion_client_bpu_0_total_line": next((line.strip() for line in (ion_client_bpu0.get("stdout") or "").splitlines() if line.strip().startswith("total ")), ""),
    "iovmm_bpu": iovmm_parsed.get("bpu"),
    "iovmm_bpu_hp": iovmm_parsed.get("bpu_hp"),
    "reserved_memory_node_count": len(reserved_memory_entries),
    "reserved_memory_summary": reserved_memory_summary,
    "default_devmem_path": default_devmem_path,
    "sudo_devmem_path": sudo_devmem_path,
    "usr_hobot_devmem_exists": usr_hobot_devmem.exists(),
    "usr_bin_devmem_exists": usr_bin_devmem.exists(),
    "busybox_has_devmem": busybox_has_devmem,
    "default_devmem_returncode": devmem_default_test.get("returncode"),
    "default_devmem_first_stderr_line": first_line(devmem_default_test.get("stderr")),
    "busybox_devmem_returncode": devmem_busybox_test.get("returncode"),
    "busybox_devmem_register_0x2b047000": first_line(devmem_busybox_test.get("stdout")),
    "perf_register_0x2b047000": first_line(perf_reg_0.get("stdout")),
    "perf_register_0x2b047004": first_line(perf_reg_1.get("stdout")),
    "performance_mode_target_applied_from_latest_retest": perf_retest.get("target_applied") if perf_retest else None,
    "latest_performance_mode_retest_path": str(perf_retest_path) if perf_retest_path else "",
    "latest_performance_mode_retest_memory_alloc_failure_observed": perf_retest.get("memory_alloc_failure_observed_after_performance_mode") if perf_retest else None,
    "ion_meminfo_returncode": ion_meminfo.get("returncode"),
    "ion_meminfo_first_stdout_line": first_line(ion_meminfo.get("stdout")),
    "ion_meminfo_shebang": ion_meminfo_shebang,
    "ion_meminfo_shebang_interpreter_exists": ion_meminfo_shebang_interpreter_exists,
    "ion_meminfo_fallback_returncode": ion_meminfo_fallback.get("returncode") if ion_meminfo_fallback else None,
    "ion_meminfo_fallback_first_stderr_line": first_line(ion_meminfo_fallback.get("stderr")) if ion_meminfo_fallback else "",
    "memstat_returncode": memstat.get("returncode"),
    "memstat_first_stdout_line": first_line(memstat.get("stdout")),
    "memstat_shebang": memstat_shebang,
    "memstat_shebang_interpreter_exists": memstat_shebang_interpreter_exists,
    "memstat_fallback_returncode": memstat_fallback.get("returncode") if memstat_fallback else None,
    "memstat_fallback_first_stdout_line": first_line(memstat_fallback.get("stdout")) if memstat_fallback else "",
    "memstat_fallback_first_stderr_line": first_line(memstat_fallback.get("stderr")) if memstat_fallback else "",
    "latest_official_qwen_runtime_report_path": str(qwen_path) if qwen_path else "",
    "latest_official_qwen_memory_alloc_failure_observed": qwen_runtime.get("memory_alloc_failure_observed") if qwen_runtime else None,
    "latest_official_qwen_runtime_returncode": qwen_runtime.get("runtime_returncode") if qwen_runtime else None,
    "latest_dream_utilization_gap_path": str(dream_util_path) if dream_util_path else "",
    "latest_dream_diagnosis": dream_util.get("diagnosis") if dream_util else None,
    "latest_dream_window3_path": str(dream_window3_path) if dream_window3_path else "",
    "latest_dream_window3_memory_alloc_failure_observed": dream_window3.get("stderr_contains_memory_alloc_failure") if dream_window3 else None,
    "allocation_failure_interpretation": (
        "reserved ION heaps are visible through debugfs, so the official Qwen failure is not explained by an absent ION debugfs heap; system/system_contig heap capacity and the exact HBMEM/UCP backend selection need a minimal allocation probe"
        if ion_heap_results.get("all_heap_info", {}).get("returncode") == 0
        else "direct ION debugfs heap data is unavailable; inspect debugfs mount/permission before interpreting official Qwen allocation failure"
    ),
    "next_probe_target": (
        "run a minimal HBMEM/UCP common-buffer allocation matrix against the exact backend/heap flags used by official Qwen; performance-mode register apply alone did not clear official Qwen allocation failure"
        if perf_retest and perf_retest.get("memory_alloc_failure_observed_after_performance_mode")
        else "run a controlled official performance-mode register apply using /usr/bin/devmem, then rerun official Qwen runtime to test whether BPU/common-buffer allocation failure changes"
    ),
    "captures": captures,
    "warnings": warnings,
    "errors": errors,
}

(run_dir / "bpu_memory_pool_probe.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
warning_lines = [f"- {item}" for item in warnings] if warnings else ["- none"]
error_lines = [f"- {item}" for item in errors] if errors else ["- none"]
lines = [
    "# S100 BPU Memory Pool Probe",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- boardid: {payload['boardid']}",
    f"- official_script_would_match_s100p: {payload['official_script_would_match_s100p']}",
    f"- performance_mode_script_action: {payload['performance_mode_script_action']}",
    f"- default_devmem_path: {payload['default_devmem_path']}",
    f"- sudo_devmem_path: {payload['sudo_devmem_path']}",
    f"- default_devmem_returncode: {payload['default_devmem_returncode']}",
    f"- default_devmem_first_stderr_line: {payload['default_devmem_first_stderr_line']}",
    f"- busybox_devmem_returncode: {payload['busybox_devmem_returncode']}",
    f"- busybox_devmem_register_0x2b047000: {payload['busybox_devmem_register_0x2b047000']}",
    f"- perf_register_0x2b047000: {payload['perf_register_0x2b047000']}",
    f"- perf_register_0x2b047004: {payload['perf_register_0x2b047004']}",
    f"- performance_mode_target_applied_from_latest_retest: {payload['performance_mode_target_applied_from_latest_retest']}",
    f"- latest_performance_mode_retest_memory_alloc_failure_observed: {payload['latest_performance_mode_retest_memory_alloc_failure_observed']}",
    f"- cmdline_contains_cma: {payload['cmdline_contains_cma']}",
    f"- cmdline_contains_ion: {payload['cmdline_contains_ion']}",
    f"- debug_mount_present: {payload['debug_mount_present']}",
    f"- ion_debug_present: {payload['ion_debug_present']}",
    f"- ion_all_heap_info_exists: {payload['ion_all_heap_info_exists']}",
    f"- system_heap_total_size: {payload['system_heap_total_size']}",
    f"- system_contig_heap_total_size: {payload['system_contig_heap_total_size']}",
    f"- cma_reserved_heap_total_size: {payload['cma_reserved_heap_total_size']}",
    f"- cma_reserved_heap_allocated_total: {payload['cma_reserved_heap_allocated_total']}",
    f"- ion_cma_heap_total_size: {payload['ion_cma_heap_total_size']}",
    f"- ion_cma_heap_allocated_total: {payload['ion_cma_heap_allocated_total']}",
    f"- carveout_heap_total_size: {payload['carveout_heap_total_size']}",
    f"- carveout_heap_allocated_total: {payload['carveout_heap_allocated_total']}",
    f"- ion_client_bpu_0_total_line: {payload['ion_client_bpu_0_total_line']}",
    f"- reserved_memory_node_count: {payload['reserved_memory_node_count']}",
    f"- iovmm_bpu_total_mappings: {(payload['iovmm_bpu'] or {}).get('total_mappings')}",
    f"- iovmm_bpu_hp_total_mappings: {(payload['iovmm_bpu_hp'] or {}).get('total_mappings')}",
    f"- ion_meminfo_returncode: {payload['ion_meminfo_returncode']}",
    f"- ion_meminfo_shebang: {payload['ion_meminfo_shebang']}",
    f"- ion_meminfo_shebang_interpreter_exists: {payload['ion_meminfo_shebang_interpreter_exists']}",
    f"- ion_meminfo_fallback_returncode: {payload['ion_meminfo_fallback_returncode']}",
    f"- memstat_returncode: {payload['memstat_returncode']}",
    f"- memstat_shebang: {payload['memstat_shebang']}",
    f"- memstat_shebang_interpreter_exists: {payload['memstat_shebang_interpreter_exists']}",
    f"- memstat_fallback_returncode: {payload['memstat_fallback_returncode']}",
    f"- latest_official_qwen_memory_alloc_failure_observed: {payload['latest_official_qwen_memory_alloc_failure_observed']}",
    f"- latest_official_qwen_runtime_returncode: {payload['latest_official_qwen_runtime_returncode']}",
    f"- latest_dream_diagnosis: {payload['latest_dream_diagnosis']}",
    f"- latest_dream_window3_memory_alloc_failure_observed: {payload['latest_dream_window3_memory_alloc_failure_observed']}",
    f"- allocation_failure_interpretation: {payload['allocation_failure_interpretation']}",
    f"- next_probe_target: {payload['next_probe_target']}",
    "",
    "## Captures",
    "",
]
lines.extend(f"- {key}: {value}" for key, value in captures.items())
lines.extend(["", "## Warnings", "", *warning_lines, "", "## Errors", "", *error_lines, ""])
(run_dir / "bpu_memory_pool_probe.md").write_text("\n".join(lines), encoding="utf-8")
print(run_dir / "bpu_memory_pool_probe.md")
if errors:
    raise SystemExit("; ".join(errors))
PY
