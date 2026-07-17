#!/usr/bin/env bash
set -euo pipefail
OUT="${1:-./validation-results}"
mkdir -p "$OUT/raw"
{
  date -u +%FT%TZ
  uname -a
  uname -m
  cat /etc/os-release
  command -v python3 || true
  command -v nmcli || true
  command -v avahi-browse || true
  command -v tailscale || true
  command -v cloudflared || true
  ip -brief address || true
  ip route || true
  nmcli device status || true
  findmnt /mnt/nas/openclaw || true
  ss -lntp || true
  df -h
  free -h
  timedatectl status || true
} > "$OUT/raw/precheck.txt" 2>&1
printf 'Precheck captured at %s\n' "$OUT/raw/precheck.txt"
