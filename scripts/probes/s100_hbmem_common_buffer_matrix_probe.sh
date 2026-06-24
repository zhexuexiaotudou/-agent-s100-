#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
sdk_root="${S100_HBMEM_MATRIX_SDK_ROOT:-/mnt/nas/openclaw/toolchains/s100_llm_sdk/D-Robotics_LLM_S100_1.0.0_SDK}"

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

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/s100_hbmem_common_buffer_matrix_$stamp"
mkdir -p "$run_dir"

src="$run_dir/hbmem_common_buffer_matrix.c"
bin="$run_dir/hbmem_common_buffer_matrix"
jsonl="$run_dir/hbmem_common_buffer_matrix.jsonl"
stdout_path="$run_dir/hbmem_common_buffer_matrix.stdout.txt"
stderr_path="$run_dir/hbmem_common_buffer_matrix.stderr.txt"

cat > "$src" <<'C'
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "hb_mem_mgr.h"
#include "hb_mem_err.h"

#ifdef WITH_UCP
#include "hobot/hb_ucp_sys.h"
#endif

typedef struct {
  const char *name;
  uint64_t size;
  int64_t flags;
} HbmemCase;

static void print_hbmem_result(const char *name, uint64_t size, int64_t flags, int32_t ret, hb_mem_common_buf_t *buf) {
  char err_buf[HB_MEM_ERR_MAX_STR_SIZE] = {0};
  hb_mem_strerror(ret, err_buf, sizeof(err_buf));
  printf("{\"api\":\"hb_mem_alloc_com_buf\",\"case_name\":\"%s\",\"size\":%llu,\"flags_hex\":\"0x%llX\",\"returncode\":%d,\"ok\":%s,\"fd\":%d,\"share_id\":%d,\"phys_addr_hex\":\"0x%llX\",\"virt_addr\":\"%p\",\"error\":\"%s\"}\n",
         name,
         (unsigned long long)size,
         (unsigned long long)flags,
         ret,
         ret == 0 ? "true" : "false",
         ret == 0 ? buf->fd : -1,
         ret == 0 ? buf->share_id : -1,
         ret == 0 ? (unsigned long long)buf->phys_addr : 0ULL,
         ret == 0 ? buf->virt_addr : NULL,
         err_buf);
}

#ifdef WITH_UCP
static void print_ucp_result(const char *api, const char *name, uint64_t size, int32_t ret, hbUCPSysMem *mem) {
  printf("{\"api\":\"%s\",\"case_name\":\"%s\",\"size\":%llu,\"returncode\":%d,\"ok\":%s,\"phyAddr_hex\":\"0x%llX\",\"virAddr\":\"%p\",\"memSize\":%llu}\n",
         api,
         name,
         (unsigned long long)size,
         ret,
         ret == 0 ? "true" : "false",
         ret == 0 ? (unsigned long long)mem->phyAddr : 0ULL,
         ret == 0 ? mem->virAddr : NULL,
         ret == 0 ? (unsigned long long)mem->memSize : 0ULL);
}
#endif

int main(void) {
  const int64_t cpu_rw = HB_MEM_USAGE_CPU_READ_OFTEN | HB_MEM_USAGE_CPU_WRITE_OFTEN;
  const int64_t map_initialized = HB_MEM_USAGE_MAP_INITIALIZED;
  const int64_t cached = HB_MEM_USAGE_CACHED;
  const int64_t hw_bpu = HB_MEM_USAGE_HW_BPU;
  const int64_t heap_dma = HB_MEM_USAGE_PRIV_HEAP_DMA;
  const int64_t heap_reserved = HB_MEM_USAGE_PRIV_HEAP_RESERVED;
  const int64_t heap_2_reserved = HB_MEM_USAGE_PRIV_HEAP_2_RESERVED;
  const uint64_t sizes[] = {4096ULL, 786432ULL, 2359296ULL, 4194304ULL};
  const struct {
    const char *name;
    int64_t flags;
  } flag_sets[] = {
      {"dma_cpu_rw_bpu_init", cpu_rw | hw_bpu | map_initialized | heap_dma},
      {"dma_cpu_rw_bpu_init_cached", cpu_rw | hw_bpu | map_initialized | cached | heap_dma},
      {"reserved_cpu_rw_bpu_init", cpu_rw | hw_bpu | map_initialized | heap_reserved},
      {"reserved_cpu_rw_bpu_init_cached", cpu_rw | hw_bpu | map_initialized | cached | heap_reserved},
      {"reserved2_cpu_rw_bpu_init", cpu_rw | hw_bpu | map_initialized | heap_2_reserved},
      {"dma_cpu_rw_init", cpu_rw | map_initialized | heap_dma},
      {"reserved_cpu_rw_init", cpu_rw | map_initialized | heap_reserved},
  };

  int32_t open_ret = hb_mem_module_open();
  printf("{\"api\":\"hb_mem_module_open\",\"returncode\":%d,\"ok\":%s}\n", open_ret, open_ret == 0 ? "true" : "false");
  if (open_ret != 0) {
    return 0;
  }

  for (size_t i = 0; i < sizeof(sizes) / sizeof(sizes[0]); ++i) {
    for (size_t j = 0; j < sizeof(flag_sets) / sizeof(flag_sets[0]); ++j) {
      hb_mem_common_buf_t buf;
      memset(&buf, 0, sizeof(buf));
      int32_t ret = hb_mem_alloc_com_buf(sizes[i], flag_sets[j].flags, &buf);
      print_hbmem_result(flag_sets[j].name, sizes[i], flag_sets[j].flags, ret, &buf);
      if (ret == 0) {
        int32_t free_ret = hb_mem_free_buf(buf.fd);
        printf("{\"api\":\"hb_mem_free_buf\",\"case_name\":\"%s\",\"size\":%llu,\"flags_hex\":\"0x%llX\",\"returncode\":%d,\"ok\":%s,\"fd\":%d}\n",
               flag_sets[j].name,
               (unsigned long long)sizes[i],
               (unsigned long long)flag_sets[j].flags,
               free_ret,
               free_ret == 0 ? "true" : "false",
               buf.fd);
      }
    }
  }

#ifdef WITH_UCP
  for (size_t i = 0; i < sizeof(sizes) / sizeof(sizes[0]); ++i) {
    hbUCPSysMem mem;
    memset(&mem, 0, sizeof(mem));
    int32_t ret = hbUCPMalloc(&mem, sizes[i], 0);
    print_ucp_result("hbUCPMalloc", "ucp_uncached", sizes[i], ret, &mem);
    if (ret == 0) {
      hbUCPFree(&mem);
    }

    memset(&mem, 0, sizeof(mem));
    ret = hbUCPMallocCached(&mem, sizes[i], 0);
    print_ucp_result("hbUCPMallocCached", "ucp_cached", sizes[i], ret, &mem);
    if (ret == 0) {
      hbUCPFree(&mem);
    }
  }
#endif

  int32_t close_ret = hb_mem_module_close();
  printf("{\"api\":\"hb_mem_module_close\",\"returncode\":%d,\"ok\":%s}\n", close_ret, close_ret == 0 ? "true" : "false");
  return 0;
}
C

compile_argv=(gcc -Wall -Wextra -O2 -I/usr/hobot/include "$src" -o "$bin" -L/usr/hobot/lib -lhbmem -lalog)
ucp_lib_dir="$sdk_root/oellm_runtime/lib"
ucp_enabled=false
if [[ -f "$ucp_lib_dir/libhbucp.so" && -f /usr/include/hobot/hb_ucp_sys.h ]]; then
  compile_argv=(gcc -Wall -Wextra -O2 -DWITH_UCP -I/usr/hobot/include -I/usr/include "$src" -o "$bin" -L/usr/hobot/lib -L"$ucp_lib_dir" -lhbmem -lhbucp -lalog)
  ucp_enabled=true
fi

{
  printf '$'
  printf ' %q' "${compile_argv[@]}"
  printf '\n'
  "${compile_argv[@]}"
} > "$run_dir/compile.stdout.txt" 2> "$run_dir/compile.stderr.txt"

set +e
LD_LIBRARY_PATH="/usr/hobot/lib:$ucp_lib_dir:${LD_LIBRARY_PATH:-}" "$bin" > "$stdout_path" 2> "$stderr_path"
run_status=$?
set -e
cp "$stdout_path" "$jsonl"

python3 - \
  "$run_dir" \
  "$jsonl" \
  "$stdout_path" \
  "$stderr_path" \
  "$src" \
  "$bin" \
  "$run_status" \
  "$ucp_enabled" <<'PY'
import json
import sys
from datetime import datetime
from pathlib import Path

run_dir = Path(sys.argv[1])
jsonl_path = Path(sys.argv[2])
stdout_path = Path(sys.argv[3])
stderr_path = Path(sys.argv[4])
src_path = Path(sys.argv[5])
bin_path = Path(sys.argv[6])
run_status = int(sys.argv[7])
ucp_enabled = sys.argv[8] == "true"

rows = []
for line in jsonl_path.read_text(encoding="utf-8", errors="replace").splitlines():
    if not line.strip():
        continue
    try:
        rows.append(json.loads(line))
    except json.JSONDecodeError:
        rows.append({"api": "unparsed", "line": line})

hbmem_rows = [row for row in rows if row.get("api") == "hb_mem_alloc_com_buf"]
ucp_rows = [row for row in rows if row.get("api") in {"hbUCPMalloc", "hbUCPMallocCached"}]
qwen_sizes = {786432, 2359296}
qwen_size_rows = [row for row in hbmem_rows if row.get("size") in qwen_sizes]
successful_hbmem_cases = [row for row in hbmem_rows if row.get("ok")]
failed_hbmem_cases = [row for row in hbmem_rows if not row.get("ok")]
successful_qwen_size_cases = [row for row in qwen_size_rows if row.get("ok")]
failed_qwen_size_cases = [row for row in qwen_size_rows if not row.get("ok")]

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_s100_hbmem_common_buffer_matrix_probe" if run_status == 0 else "failed_s100_hbmem_common_buffer_matrix_probe",
    "run_dir": str(run_dir),
    "source_path": str(src_path),
    "binary_path": str(bin_path),
    "jsonl_path": str(jsonl_path),
    "stdout_path": str(stdout_path),
    "stderr_path": str(stderr_path),
    "run_status": run_status,
    "ucp_enabled": ucp_enabled,
    "row_count": len(rows),
    "hbmem_alloc_case_count": len(hbmem_rows),
    "hbmem_alloc_success_count": len(successful_hbmem_cases),
    "hbmem_alloc_failure_count": len(failed_hbmem_cases),
    "qwen_log_size_case_count": len(qwen_size_rows),
    "qwen_log_size_success_count": len(successful_qwen_size_cases),
    "qwen_log_size_failure_count": len(failed_qwen_size_cases),
    "qwen_log_sizes": sorted(qwen_sizes),
    "successful_qwen_size_cases": successful_qwen_size_cases,
    "failed_qwen_size_cases": failed_qwen_size_cases,
    "ucp_case_count": len(ucp_rows),
    "ucp_success_count": len([row for row in ucp_rows if row.get("ok")]),
    "next_probe_target": "compare these direct HBMEM/UCP allocation results with official Qwen's backend: 9 failure path and inspect libhbucp backend-to-hbmem flag selection if direct allocations pass",
    "errors": [] if run_status == 0 else [f"matrix binary exited with {run_status}"],
}
(run_dir / "hbmem_common_buffer_matrix_probe.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
lines = [
    "# S100 HBMEM Common Buffer Matrix Probe",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- run_status: {payload['run_status']}",
    f"- ucp_enabled: {payload['ucp_enabled']}",
    f"- hbmem_alloc_case_count: {payload['hbmem_alloc_case_count']}",
    f"- hbmem_alloc_success_count: {payload['hbmem_alloc_success_count']}",
    f"- qwen_log_sizes: {payload['qwen_log_sizes']}",
    f"- qwen_log_size_success_count: {payload['qwen_log_size_success_count']}",
    f"- qwen_log_size_failure_count: {payload['qwen_log_size_failure_count']}",
    f"- ucp_case_count: {payload['ucp_case_count']}",
    f"- ucp_success_count: {payload['ucp_success_count']}",
    f"- jsonl_path: {payload['jsonl_path']}",
    f"- next_probe_target: {payload['next_probe_target']}",
    "",
    "## Errors",
    "",
]
if payload["errors"]:
    lines.extend(f"- {item}" for item in payload["errors"])
else:
    lines.append("- none")
(run_dir / "hbmem_common_buffer_matrix_probe.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(run_dir / "hbmem_common_buffer_matrix_probe.md")
if payload["errors"]:
    raise SystemExit("; ".join(payload["errors"]))
PY
