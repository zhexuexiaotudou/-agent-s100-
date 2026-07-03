#!/usr/bin/env bash
set -euo pipefail

input_dir="${1:-/mnt/nas/openclaw/documents}"
out_dir="${2:-}"

case "$input_dir" in
  ""|"/"|"/root"|"/home"|"/mnt"|"/mnt/nas")
    echo "Refusing unsafe input directory: $input_dir" >&2
    exit 2
    ;;
esac

case "$input_dir" in
  /tmp/*|/mnt/nas/openclaw/documents|/mnt/nas/openclaw/documents/*|/root/.openclaw/workspace/documents|/root/.openclaw/workspace/documents/*) ;;
  *)
    echo "Refusing input path outside approved document directories: $input_dir" >&2
    exit 2
    ;;
esac

if [[ ! -d "$input_dir" ]]; then
  echo "Input directory does not exist: $input_dir" >&2
  exit 3
fi

if [[ -z "$out_dir" ]]; then
  if [[ -d /mnt/nas/openclaw/reports && -w /mnt/nas/openclaw/reports ]]; then
    out_dir="/mnt/nas/openclaw/reports"
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

case "$out_dir" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/mnt/nas/openclaw/logs/probes|/mnt/nas/openclaw/logs/probes/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*|/root/.openclaw/workspace/logs/probes|/root/.openclaw/workspace/logs/probes/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $out_dir" >&2
    exit 2
    ;;
esac

mkdir -p "$out_dir"
stamp="$(date +%Y%m%d-%H%M%S)"
report="$out_dir/document_index_$stamp.md"
tmp_list="$(mktemp)"
trap 'rm -f "$tmp_list"' EXIT

find "$input_dir" -maxdepth 4 -type f \
  \( -name '*.md' -o -name '*.txt' -o -name '*.json' -o -name '*.yaml' -o -name '*.yml' -o -name '*.csv' \) \
  -size -10M -print | sort > "$tmp_list"

count="$(wc -l < "$tmp_list" | tr -d ' ')"

{
  echo "# Document Index"
  echo
  echo "- timestamp: $(date -Is)"
  echo "- input_dir: $input_dir"
  echo "- indexed_files: $count"
  echo
  echo "| Path | Size | Modified | SHA256 | Preview |"
  echo "| --- | ---: | --- | --- | --- |"
  while IFS= read -r file; do
    rel="${file#$input_dir/}"
    size="$(stat -c '%s' "$file" 2>/dev/null || echo 0)"
    mtime="$(stat -c '%y' "$file" 2>/dev/null | cut -d'.' -f1 || true)"
    hash="$(sha256sum "$file" 2>/dev/null | awk '{print $1}' || true)"
    preview="$(tr '\n' ' ' < "$file" | sed -E 's/[|`]/ /g; s/[[:space:]]+/ /g' | cut -c 1-160)"
    printf '| `%s` | %s | %s | `%s` | %s |\n' "$rel" "$size" "$mtime" "$hash" "$preview"
  done < "$tmp_list"
} > "$report"

echo "$report"
