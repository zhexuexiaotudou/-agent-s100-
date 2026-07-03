#!/usr/bin/env bash
set -euo pipefail

out_dir="${1:-${OPENCLAW_PROBE_DIR:-/tmp/openclaw-probes}}"

case "$out_dir" in
  /tmp/*|/mnt/nas/openclaw/logs/probes|/mnt/nas/openclaw/logs/probes/*|/root/.openclaw/workspace/logs/probes|/root/.openclaw/workspace/logs/probes/*) ;;
  *)
    echo "Refusing output path outside approved probe directories: $out_dir" >&2
    exit 2
    ;;
esac

mkdir -p "$out_dir"
stamp="$(date +%Y%m%d-%H%M%S)"
report="$out_dir/sandbox_isolation_smoke_$stamp.md"
json="$out_dir/sandbox_isolation_smoke_$stamp.json"
tmp_dir="/tmp/openclaw-a006-smoke-$stamp"
mkdir -p "$tmp_dir"
trap 'rm -rf "$tmp_dir"' EXIT

runtime="missing"
runtime_detail="no docker or podman command available"
image="missing"
verdict="blocked_runtime_missing"
smoke_exit="not_run"
smoke_output="not_run"
allowed_file="$tmp_dir/allowed.txt"

if command -v docker >/dev/null 2>&1 && systemctl is-active docker >/dev/null 2>&1; then
  runtime="docker"
  runtime_detail="$(command -v docker)"
elif command -v podman >/dev/null 2>&1; then
  runtime="podman"
  runtime_detail="$(command -v podman)"
fi

local_images() {
  case "$runtime" in
    docker)
      docker image ls --format '{{.Repository}}:{{.Tag}}' 2>/dev/null | grep -vE '^<none>|:<none>$' || true
      ;;
    podman)
      podman image ls --format '{{.Repository}}:{{.Tag}}' 2>/dev/null | grep -vE '^<none>|:<none>$' || true
      ;;
  esac
}

if [[ "$runtime" != "missing" ]]; then
  image="$(local_images | head -1 || true)"
  if [[ -z "$image" ]]; then
    image="missing"
    verdict="blocked_no_local_image"
    smoke_output="runtime exists but no local image is available; this probe does not pull images"
  else
    smoke_script='set -eu
test -d /allowed
echo ok > /allowed/probe.txt
test ! -e /host_root
test ! -e /host_workspace
test ! -e /host_ssh
test ! -e /host_nas
test "$(cat /allowed/probe.txt)" = ok
echo isolated_smoke_ok'
    if [[ "$runtime" == "docker" ]]; then
      set +e
      smoke_output="$(timeout 25 docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=16m -v "$tmp_dir:/allowed:rw" "$image" sh -c "$smoke_script" 2>&1)"
      smoke_exit=$?
      set -e
    else
      set +e
      smoke_output="$(timeout 25 podman run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=16m -v "$tmp_dir:/allowed:rw" "$image" sh -c "$smoke_script" 2>&1)"
      smoke_exit=$?
      set -e
    fi
    if [[ "$smoke_exit" == "0" && -f "$allowed_file" && "$(cat "$allowed_file" 2>/dev/null || true)" == "ok" ]]; then
      verdict="ok_isolated"
    else
      verdict="failed_smoke"
    fi
  fi
fi

python3 - "$json" "$stamp" "$runtime" "$runtime_detail" "$image" "$verdict" "$smoke_exit" "$report" <<'PY'
import json
import sys
from datetime import datetime

json_path, stamp, runtime, runtime_detail, image, verdict, smoke_exit, report = sys.argv[1:]
payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "stamp": stamp,
    "mode": "bounded sandbox isolation smoke; no package install, no image pull",
    "runtime": runtime,
    "runtime_detail": runtime_detail,
    "image": image,
    "verdict": verdict,
    "smoke_exit": smoke_exit,
    "report": report,
}
with open(json_path, "w", encoding="utf-8") as fh:
    json.dump(payload, fh, ensure_ascii=False, indent=2)
    fh.write("\n")
PY

{
  echo "# A-006 Sandbox Isolation Smoke"
  echo
  echo "- generated_at: $(date -Is)"
  echo "- mode: bounded sandbox isolation smoke; no package install, no image pull"
  echo "- report: $report"
  echo "- json: $json"
  echo "- runtime: $runtime"
  echo "- runtime_detail: $runtime_detail"
  echo "- image: $image"
  echo "- verdict: $verdict"
  echo "- smoke_exit: $smoke_exit"
  echo
  echo "## Boundary"
  echo
  echo "- This probe does not install Docker, Podman, runc, containerd, or images."
  echo "- This probe does not pull images from a registry."
  echo "- If a runtime and local image exist, it runs with network disabled, a read-only container filesystem, a temporary tmpfs, and exactly one writable temporary host mount."
  echo
  echo "## Smoke Output"
  echo
  echo '```text'
  printf '%s\n' "$smoke_output"
  echo '```'
  echo
  echo "## A-006 Meaning"
  echo
  case "$verdict" in
    ok_isolated)
      echo "- isolation_verdict: pass"
      echo "- next_check: keep this smoke current after runtime, image, or mount-policy changes."
      ;;
    blocked_runtime_missing)
      echo "- isolation_verdict: blocked_runtime"
      echo "- next_check: install Docker/Podman/runc or explicitly drop A-006 from baseline v1."
      ;;
    blocked_no_local_image)
      echo "- isolation_verdict: blocked_no_local_image"
      echo "- next_check: provide an approved local shell-capable image, then rerun this smoke."
      ;;
    *)
      echo "- isolation_verdict: failed"
      echo "- next_check: inspect smoke output and runtime logs before considering A-006 verified."
      ;;
  esac
} > "$report"

echo "$report"
