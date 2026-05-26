#!/usr/bin/env bash
set -euo pipefail

out_dir="${1:-${OPENCLAW_REPORT_DIR:-/root/.openclaw/workspace/reports/browser-smoke}}"

case "$out_dir" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $out_dir" >&2
    exit 2
    ;;
esac

workspace="${OPENCLAW_WORKSPACE_DIR:-/root/.openclaw/workspace}"
page_dir="$workspace/browser-smoke"
snap_out="/root/snap/chromium/common/openclaw-browser-smoke"
timestamp="$(date +%Y%m%d-%H%M%S)"
url="http://127.0.0.1:18080/index.html"
report="$out_dir/browser_smoke_$timestamp.md"
screenshot="$out_dir/browser_smoke_$timestamp.png"
snap_screenshot="$snap_out/browser_smoke_$timestamp.png"
log_file="$out_dir/browser_smoke_$timestamp.log"

mkdir -p "$out_dir" "$page_dir" "$snap_out"

cat > "$page_dir/index.html" <<'HTML'
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>OpenClaw S100P Browser Smoke</title>
  <style>
    body { font-family: sans-serif; margin: 40px; background: #f7fafc; color: #1f2937; }
    main { max-width: 760px; border: 1px solid #cbd5e1; border-radius: 8px; padding: 24px; background: white; }
    .status { display: inline-block; padding: 6px 10px; background: #dcfce7; color: #166534; border-radius: 999px; font-weight: 700; }
  </style>
</head>
<body>
  <main>
    <h1>OpenClaw S100P Browser Smoke</h1>
    <p class="status">BROWSER_SMOKE_READY</p>
    <p id="target">If this text is visible in a screenshot, browser automation opened the local test page.</p>
  </main>
</body>
</html>
HTML

if [[ -f /tmp/openclaw_browser_smoke.pid ]] && kill -0 "$(cat /tmp/openclaw_browser_smoke.pid)" 2>/dev/null; then
  server_status="already_running"
else
  (
    cd "$page_dir"
    nohup python3 -m http.server 18080 --bind 127.0.0.1 >/tmp/openclaw_browser_smoke.log 2>&1 &
    echo "$!" >/tmp/openclaw_browser_smoke.pid
  )
  sleep 1
  server_status="started"
fi

if curl -fsS "$url" | grep -q 'BROWSER_SMOKE_READY'; then
  visible_marker="yes"
else
  visible_marker="no"
fi

if command -v chromium-browser >/dev/null 2>&1; then
  browser_cmd="$(command -v chromium-browser)"
elif command -v chromium >/dev/null 2>&1; then
  browser_cmd="$(command -v chromium)"
else
  browser_cmd=""
fi

verdict="failed"
screenshot_status="not_captured"
png_magic=""
browser_version=""

if [[ -n "$browser_cmd" ]]; then
  browser_version="$("$browser_cmd" --version 2>/dev/null || true)"
  rm -f "$snap_screenshot"
  if timeout 60 "$browser_cmd" \
    --headless \
    --no-sandbox \
    --disable-gpu \
    --disable-dev-shm-usage \
    --screenshot="$snap_screenshot" \
    "$url" >"$log_file" 2>&1; then
    if [[ -s "$snap_screenshot" ]]; then
      cp "$snap_screenshot" "$screenshot"
      png_magic="$(python3 - "$screenshot" <<'PY'
from pathlib import Path
import sys
p = Path(sys.argv[1])
print(p.read_bytes()[:8].hex() if p.exists() else "")
PY
)"
      if [[ "$png_magic" == "89504e470d0a1a0a" && "$visible_marker" == "yes" ]]; then
        screenshot_status="captured"
        verdict="ok"
      else
        screenshot_status="invalid_png"
      fi
    else
      screenshot_status="missing_file"
    fi
  else
    screenshot_status="browser_command_failed"
  fi
else
  screenshot_status="no_chromium"
fi

{
  echo "# Browser Smoke"
  echo
  echo "- generated_at: $(date -Is)"
  echo "- url: $url"
  echo "- server_status: $server_status"
  echo "- browser_cmd: ${browser_cmd:-missing}"
  echo "- browser_version: ${browser_version:-unknown}"
  echo "- visible_marker: $visible_marker"
  echo "- screenshot_status: $screenshot_status"
  echo "- screenshot_path: $screenshot"
  echo "- png_magic: ${png_magic:-none}"
  echo "- verdict: $verdict"
  echo
  echo "## Browser Log"
  echo
  echo '```text'
  sed -n '1,80p' "$log_file" 2>/dev/null || true
  echo '```'
} > "$report"

echo "$report"
