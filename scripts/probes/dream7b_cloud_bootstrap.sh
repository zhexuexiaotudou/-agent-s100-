#!/usr/bin/env bash
set -euo pipefail

DATA_ROOT="${DATA_ROOT:-/data}"
WORK_ROOT="${WORK_ROOT:-$DATA_ROOT/dream7b-cloud}"
DATA_DISK="${DATA_DISK:-}"
FORMAT_DATA_DISK="${FORMAT_DATA_DISK:-0}"
INSTALL_DOCKER="${INSTALL_DOCKER:-0}"
SDK_OELLM_BUILD="${SDK_OELLM_BUILD:-}"
VENV_DIR="${VENV_DIR:-$WORK_ROOT/venvs/oellm}"
REPORT_DIR="${REPORT_DIR:-$WORK_ROOT/reports/bootstrap_$(date +%Y%m%d-%H%M%S)}"

mkdir -p "$REPORT_DIR"
exec > >(tee -a "$REPORT_DIR/bootstrap.log") 2>&1

echo "bootstrap_report_dir=$REPORT_DIR"
echo "data_root=$DATA_ROOT"
echo "work_root=$WORK_ROOT"

if [[ "$(uname -m)" != "x86_64" ]]; then
  echo "ERROR: expected x86_64 host, got $(uname -m)" >&2
  exit 2
fi

echo "== block devices =="
lsblk -o NAME,TYPE,SIZE,FSTYPE,MOUNTPOINT,MODEL

if ! mountpoint -q "$DATA_ROOT"; then
  if [[ -n "$DATA_DISK" && "$FORMAT_DATA_DISK" == "1" ]]; then
    if [[ ! -b "$DATA_DISK" ]]; then
      echo "ERROR: DATA_DISK is not a block device: $DATA_DISK" >&2
      exit 2
    fi
    root_source="$(findmnt -n -o SOURCE / || true)"
    disk_mounts="$(lsblk -nr -o MOUNTPOINT "$DATA_DISK" | grep -v '^$' || true)"
    disk_size_bytes="$(blockdev --getsize64 "$DATA_DISK")"
    min_size_bytes=$((900 * 1024 * 1024 * 1024))
    if [[ "$DATA_DISK" == "$root_source" || -n "$disk_mounts" || "$disk_size_bytes" -lt "$min_size_bytes" ]]; then
      echo "ERROR: refusing to format suspicious disk DATA_DISK=$DATA_DISK root_source=$root_source mounts=$disk_mounts size=$disk_size_bytes" >&2
      exit 2
    fi
    echo "Formatting $DATA_DISK as ext4 and mounting at $DATA_ROOT"
    mkfs.ext4 -F "$DATA_DISK"
    mkdir -p "$DATA_ROOT"
    mount "$DATA_DISK" "$DATA_ROOT"
    uuid="$(blkid -s UUID -o value "$DATA_DISK")"
    if [[ -n "$uuid" ]] && ! grep -q "$uuid" /etc/fstab; then
      echo "UUID=$uuid $DATA_ROOT ext4 defaults,nofail 0 2" >> /etc/fstab
    fi
  else
    mkdir -p "$DATA_ROOT"
    echo "WARN: $DATA_ROOT is not a mountpoint. Set DATA_DISK=/dev/xxx FORMAT_DATA_DISK=1 to format and mount the cloud data disk."
  fi
fi

mkdir -p "$WORK_ROOT"/{input,workspace,outputs,reports,tmp,venvs,logs}
chmod 1777 "$WORK_ROOT/tmp"

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y \
  aria2 bc build-essential ca-certificates curl git git-lfs htop iotop jq lsof \
  ncdu net-tools numactl pigz procps python3.10 python3.10-venv python3-pip \
  rsync sysstat tmux unzip vim wget zip zstd

if [[ "$INSTALL_DOCKER" == "1" ]]; then
  apt-get install -y docker.io
  systemctl enable --now docker || true
fi

python3.10 - "$REPORT_DIR/machine_report.json" "$DATA_ROOT" "$WORK_ROOT" <<'PY'
from __future__ import annotations

import json
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def run(command: list[str]) -> dict[str, object]:
    completed = subprocess.run(command, text=True, capture_output=True)
    return {
        "args": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def mem_total_gib() -> float:
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemTotal:"):
            return int(line.split()[1]) / 1024 / 1024
    return 0.0


payload = {
    "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
    "platform": platform.platform(),
    "machine": platform.machine(),
    "python": platform.python_version(),
    "mem_total_gib": round(mem_total_gib(), 3),
    "cpu_count": run(["nproc"]),
    "lsblk": run(["lsblk", "-o", "NAME,TYPE,SIZE,FSTYPE,MOUNTPOINT,MODEL"]),
    "df": run(["df", "-hT", sys.argv[2], sys.argv[3], "/"]),
    "data_usage": shutil.disk_usage(sys.argv[2])._asdict(),
}
Path(sys.argv[1]).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(payload, ensure_ascii=False, indent=2))
PY

if [[ -n "$SDK_OELLM_BUILD" ]]; then
  if [[ ! -d "$SDK_OELLM_BUILD" ]]; then
    echo "ERROR: SDK_OELLM_BUILD not found: $SDK_OELLM_BUILD" >&2
    exit 2
  fi
  python3.10 -m venv "$VENV_DIR"
  # shellcheck source=/dev/null
  source "$VENV_DIR/bin/activate"
  python -m pip install --upgrade pip wheel setuptools
  python -m pip install -r "$SDK_OELLM_BUILD/requirements.txt"
  python -m pip install "$SDK_OELLM_BUILD"/hbdk4_compiler-*.whl "$SDK_OELLM_BUILD"/leap_llm-*.whl
  python - <<'PY'
import platform
import hbdk4
import leap_llm
print("python", platform.python_version(), platform.machine())
print("hbdk4", getattr(hbdk4, "__version__", "unknown"))
print("leap_llm imported")
PY
fi

echo "verdict=bootstrap_finished"
