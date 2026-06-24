#!/usr/bin/env bash
set -euo pipefail

REPORT_DIR="${1:-${REPORT_DIR:-/data/dream7b-cloud/reports/resource_monitor_$(date +%Y%m%d-%H%M%S)}}"
INTERVAL_SECONDS="${INTERVAL_SECONDS:-30}"

mkdir -p "$REPORT_DIR"
LOG_JSONL="$REPORT_DIR/resource_trace.jsonl"
TOP_LOG="$REPORT_DIR/top_snapshots.log"

echo "resource_monitor_report_dir=$REPORT_DIR"
echo "resource_monitor_interval_seconds=$INTERVAL_SECONDS"

while true; do
  python3 - "$LOG_JSONL" <<'PY'
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def run(cmd: list[str]) -> str:
    try:
        return subprocess.run(cmd, text=True, capture_output=True, timeout=10).stdout.strip()
    except Exception as exc:
        return f"ERROR:{type(exc).__name__}:{exc}"


def meminfo() -> dict[str, int]:
    out: dict[str, int] = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        if ":" not in line:
            continue
        key, raw = line.split(":", 1)
        parts = raw.strip().split()
        if parts and parts[0].isdigit():
            out[key] = int(parts[0]) * 1024
    return out


payload = {
    "ts": datetime.now(timezone.utc).astimezone().isoformat(),
    "loadavg": Path("/proc/loadavg").read_text().strip() if Path("/proc/loadavg").exists() else "",
    "meminfo": meminfo(),
    "df": run(["df", "-B1", "-T", "/data", "/tmp", "/"]),
    "iostat": run(["bash", "-lc", "command -v iostat >/dev/null && iostat -xz 1 1 || true"]),
    "top_rss": run(["bash", "-lc", "ps -eo pid,ppid,comm,rss,vsz,etime,args --sort=-rss | head -30"]),
}
with open(sys.argv[1], "a", encoding="utf-8") as handle:
    handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
PY
  {
    echo "===== $(date --iso-8601=seconds) ====="
    ps -eo pid,ppid,comm,%cpu,%mem,rss,vsz,etime,args --sort=-rss | head -40
    echo
  } >> "$TOP_LOG"
  sleep "$INTERVAL_SECONDS"
done
