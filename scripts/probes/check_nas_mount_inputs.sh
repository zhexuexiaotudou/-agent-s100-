#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/probes/check_nas_mount_inputs.sh --protocol smb --host <ip-or-host> --share <share-name> [--mountpoint /mnt/nas/openclaw]
  scripts/probes/check_nas_mount_inputs.sh --protocol nfs --host <ip-or-host> --share <export-path> [--mountpoint /mnt/nas/openclaw]

This is a read-only preflight. It checks inputs, tools, port reachability, and
mountpoint safety. It does not mount the NAS and never asks for a password.
EOF
}

protocol=""
host=""
share=""
mountpoint="/mnt/nas/openclaw"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --protocol)
      protocol="${2:-}"
      shift 2
      ;;
    --host)
      host="${2:-}"
      shift 2
      ;;
    --share)
      share="${2:-}"
      shift 2
      ;;
    --mountpoint)
      mountpoint="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

case "$protocol" in
  smb|nfs) ;;
  "")
    echo "Missing --protocol" >&2
    usage >&2
    exit 2
    ;;
  *)
    echo "Unsupported protocol: $protocol" >&2
    exit 2
    ;;
esac

if [[ -z "$host" || -z "$share" ]]; then
  echo "Missing --host or --share" >&2
  usage >&2
  exit 2
fi

case "$mountpoint" in
  /mnt/nas/openclaw|/mnt/nas/openclaw/*) ;;
  *)
    echo "Refusing mountpoint outside /mnt/nas/openclaw: $mountpoint" >&2
    exit 2
    ;;
esac

echo "protocol=$protocol"
echo "host=$host"
echo "share=$share"
echo "mountpoint=$mountpoint"
echo

echo "## host reachability"
if ping -c 1 -W 2 "$host" >/dev/null 2>&1; then
  echo "ping=ok"
else
  echo "ping=failed"
fi

echo
echo "## dependency checks"
if [[ "$protocol" == "smb" ]]; then
  command -v mount.cifs >/dev/null 2>&1 && echo "mount.cifs=ok" || echo "mount.cifs=missing"
  timeout 3 bash -c "cat < /dev/null > /dev/tcp/$host/445" >/dev/null 2>&1 && echo "tcp_445=ok" || echo "tcp_445=failed"
  echo "suggested_source=//$host/$share"
else
  command -v mount.nfs >/dev/null 2>&1 && echo "mount.nfs=ok" || echo "mount.nfs=missing"
  timeout 3 bash -c "cat < /dev/null > /dev/tcp/$host/2049" >/dev/null 2>&1 && echo "tcp_2049=ok" || echo "tcp_2049=failed"
  echo "suggested_source=$host:$share"
fi

echo
echo "## mountpoint checks"
if [[ -e "$mountpoint" ]]; then
  if [[ -d "$mountpoint" ]]; then
    echo "mountpoint_exists=directory"
  else
    echo "mountpoint_exists=not_directory"
  fi
else
  echo "mountpoint_exists=no"
fi

if findmnt "$mountpoint" >/dev/null 2>&1; then
  echo "already_mounted=yes"
else
  echo "already_mounted=no"
fi

echo
echo "PREFLIGHT_DONE"
