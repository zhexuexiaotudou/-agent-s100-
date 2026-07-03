#!/usr/bin/env bash
set -euo pipefail

log_dir="${1:-/tmp/openclaw}"
out_dir="${2:-}"

case "$log_dir" in
  ""|"/"|"/root"|"/home"|"/mnt"|"/mnt/nas")
    echo "Refusing unsafe log directory: $log_dir" >&2
    exit 2
    ;;
esac

if [[ ! -d "$log_dir" ]]; then
  echo "Log directory does not exist: $log_dir" >&2
  exit 3
fi

if [[ -z "$out_dir" ]]; then
  if [[ -d /mnt/nas/openclaw/logs/probes && -w /mnt/nas/openclaw/logs/probes ]]; then
    out_dir="/mnt/nas/openclaw/logs/probes"
  else
    out_dir="/tmp/openclaw-probes"
  fi
fi

case "$out_dir" in
  ""|"/"|"/mnt"|"/mnt/nas"|"/home"|"/root")
    echo "Refusing unsafe output directory: $out_dir" >&2
    exit 2
    ;;
esac

mkdir -p "$out_dir"
stamp="$(date +%Y%m%d-%H%M%S)"
report="$out_dir/log_diagnosis_$stamp.md"

tmp_matches="$(mktemp)"
trap 'rm -f "$tmp_matches"' EXIT

find "$log_dir" -maxdepth 2 -type f \
  \( -name '*.log' -o -name '*.txt' -o -name '*.jsonl' \) \
  -size -20M -print0 |
  xargs -0 grep -HniE 'error|exception|failed|denied|timeout|refused|oom|traceback|fatal|permission|not found' \
  > "$tmp_matches" 2>/dev/null || true

total_matches="$(wc -l < "$tmp_matches" | tr -d ' ')"

{
  echo "# Log Diagnosis"
  echo
  echo "- timestamp: $(date -Is)"
  echo "- log_dir: $log_dir"
  echo "- total_matches: $total_matches"
  echo
  echo "## Top Error Patterns"
  if [[ "$total_matches" -eq 0 ]]; then
    echo
    echo "No obvious error patterns were found."
  else
    awk '
      BEGIN { IGNORECASE=1 }
      /permission|denied/ { c["permission denied"]++ }
      /timeout|timed out/ { c["timeout"]++ }
      /refused/ { c["connection refused"]++ }
      /not found|command not found/ { c["not found"]++ }
      /oom|out of memory/ { c["out of memory"]++ }
      /traceback|exception|fatal/ { c["exception/fatal"]++ }
      /failed|error/ { c["generic error/failed"]++ }
      END {
        for (k in c) printf("- %s: %d\n", k, c[k]);
      }
    ' "$tmp_matches" | sort || true
  fi
  echo
  echo "## Recent Matches"
  echo
  if [[ "$total_matches" -eq 0 ]]; then
    echo "None."
  else
    tail -40 "$tmp_matches" | sed -E 's/(tvly-[A-Za-z0-9_-]+)/***TAVILY_KEY***/g; s/(api[_-]?key|secret|token|authorization)[=: ][^ ]+/\1=***/Ig'
  fi
  echo
  echo "## Suggested Checks"
  echo
  echo '```bash'
  echo "systemctl --user --no-pager --full status openclaw-gateway"
  echo "tail -120 /tmp/openclaw/openclaw-\$(date +%F).log"
  echo "ss -ltnp | grep 18789"
  echo "mount | grep /mnt/nas/openclaw"
  echo '```'
} > "$report"

echo "$report"
