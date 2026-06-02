#!/usr/bin/env bash
set -euo pipefail

# Verify whether the current Linux host can run the S100 HBDK/oellm compiler.
# This is a build-host probe, not a runtime probe. S100P can run the produced
# HBM, but the compiler wheel is x86_64 Linux only and may require AVX.

VENV_DIR="${VENV_DIR:-/mnt/nas/openclaw/tmp/dream-s100-oellm-venv}"
REQUIRE_HBDK_IMPORT="${REQUIRE_HBDK_IMPORT:-0}"

arch="$(uname -m)"
flags="$(grep -m1 '^flags' /proc/cpuinfo 2>/dev/null || true)"

echo "Builder compatibility:"
echo "  arch: $arch"
echo "  python3.10: $(command -v python3.10 || true)"
echo "  cpu_flags_has_avx: $(grep -qw avx <<<"$flags" && echo yes || echo no)"
echo "  cpu_flags_has_avx2: $(grep -qw avx2 <<<"$flags" && echo yes || echo no)"

if [[ "$arch" != "x86_64" ]]; then
  echo "verdict: blocked_non_x86_64"
  exit 2
fi

if ! command -v python3.10 >/dev/null 2>&1; then
  echo "verdict: blocked_no_python3_10"
  exit 2
fi

if ! grep -qw avx <<<"$flags"; then
  echo "verdict: blocked_no_avx"
  exit 2
fi

if [[ "$REQUIRE_HBDK_IMPORT" == "1" ]]; then
  if [[ ! -x "$VENV_DIR/bin/python" ]]; then
    echo "verdict: blocked_missing_venv"
    exit 2
  fi

  "$VENV_DIR/bin/python" -X faulthandler - <<'PY'
import hbdk4.compiler
import torch
print("hbdk4.compiler import ok")
print("torch", torch.__version__)
PY
fi

echo "verdict: ok_builder_candidate"
