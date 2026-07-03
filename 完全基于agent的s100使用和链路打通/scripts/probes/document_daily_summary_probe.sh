#!/usr/bin/env bash
set -euo pipefail

documents_dir="${1:-/mnt/nas/openclaw/documents}"
report_dir="${2:-}"

case "$documents_dir" in
  /tmp/*|/mnt/nas/openclaw/documents|/mnt/nas/openclaw/documents/*|/root/.openclaw/workspace/documents|/root/.openclaw/workspace/documents/*) ;;
  *)
    echo "Refusing document path outside approved directories: $documents_dir" >&2
    exit 2
    ;;
esac

if [[ ! -d "$documents_dir" ]]; then
  echo "Documents directory does not exist: $documents_dir" >&2
  exit 3
fi

if [[ -z "$report_dir" ]]; then
  if [[ -d /mnt/nas/openclaw/reports && -w /mnt/nas/openclaw/reports ]]; then
    report_dir="/mnt/nas/openclaw/reports/daily-summary"
  else
    report_dir="/root/.openclaw/workspace/reports/daily-summary"
  fi
fi

case "$report_dir" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_dir" >&2
    exit 2
    ;;
esac

mkdir -p "$report_dir"
stamp="$(date +%Y%m%d-%H%M%S)"
report="$report_dir/document_daily_summary_$stamp.md"
json="$report_dir/document_daily_summary_$stamp.json"

tmp_script="$(mktemp)"
trap 'rm -f "$tmp_script"' EXIT

cat > "$tmp_script" <<'PY'
import collections
import hashlib
import json
import os
import sys
import time
from pathlib import Path

documents_dir = Path(sys.argv[1])
report_path = Path(sys.argv[2])
json_path = Path(sys.argv[3])

allowed_ext = {".md", ".txt", ".json", ".yaml", ".yml", ".csv"}
now = time.time()
day_ago = now - 86400


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def preview(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    return " ".join(text.split())[:220].replace("|", " ")


records = []
for path in sorted(documents_dir.rglob("*")):
    if not path.is_file() or path.suffix.lower() not in allowed_ext:
        continue
    stat = path.stat()
    rel = path.relative_to(documents_dir).as_posix()
    records.append({
        "relative_path": rel,
        "bytes": stat.st_size,
        "mtime": int(stat.st_mtime),
        "mtime_iso": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime)),
        "modified_last_24h": stat.st_mtime >= day_ago,
        "directory": rel.split("/", 1)[0] if "/" in rel else ".",
        "sha256": sha256_file(path),
        "preview": preview(path),
    })

records.sort(key=lambda item: (item["mtime"], item["relative_path"]), reverse=True)
modified = [item for item in records if item["modified_last_24h"]]
dir_counts = collections.Counter(item["directory"] for item in records)
ext_counts = collections.Counter(Path(item["relative_path"]).suffix.lower() or "(none)" for item in records)

summary = {
    "documents_dir": str(documents_dir),
    "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(now)),
    "total_documents": len(records),
    "modified_last_24h": len(modified),
    "total_bytes": sum(item["bytes"] for item in records),
    "top_directories": dir_counts.most_common(10),
    "extension_counts": ext_counts.most_common(10),
    "latest_documents": records[:10],
}

json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

with report_path.open("w", encoding="utf-8") as out:
    out.write("# Document Daily Summary\n\n")
    out.write(f"- generated_at: {summary['generated_at']}\n")
    out.write(f"- documents_dir: {documents_dir}\n")
    out.write(f"- report: {report_path}\n")
    out.write(f"- json: {json_path}\n")
    out.write("- mode: deterministic file metadata summary; no external model used\n\n")

    out.write("## Summary\n\n")
    out.write("| Check | Value |\n")
    out.write("| --- | ---: |\n")
    out.write(f"| Total documents | {summary['total_documents']} |\n")
    out.write(f"| Modified last 24h | {summary['modified_last_24h']} |\n")
    out.write(f"| Total bytes | {summary['total_bytes']} |\n\n")

    out.write("## Top Directories\n\n")
    out.write("| Directory | Files |\n")
    out.write("| --- | ---: |\n")
    if summary["top_directories"]:
        for directory, count in summary["top_directories"]:
            out.write(f"| `{directory}` | {count} |\n")
    else:
        out.write("| none | 0 |\n")
    out.write("\n")

    out.write("## File Types\n\n")
    out.write("| Extension | Files |\n")
    out.write("| --- | ---: |\n")
    if summary["extension_counts"]:
        for ext, count in summary["extension_counts"]:
            out.write(f"| `{ext}` | {count} |\n")
    else:
        out.write("| none | 0 |\n")
    out.write("\n")

    out.write("## Latest Documents\n\n")
    if records:
        out.write("| Path | Modified | Size | SHA256 | Preview |\n")
        out.write("| --- | --- | ---: | --- | --- |\n")
        for item in records[:10]:
            out.write(
                f"| `{item['relative_path']}` | {item['mtime_iso']} | {item['bytes']} | "
                f"`{item['sha256'][:16]}` | {item['preview']} |\n"
            )
    else:
        out.write("No supported document files found.\n")
    out.write("\n")

    out.write("## B-002 Acceptance\n\n")
    if records:
        out.write("- Document daily summary generation is available for the current documents directory.\n")
        out.write("- This is a deterministic metadata summary; semantic/LLM summarization can be added later if needed.\n")
    else:
        out.write("- No documents were available to summarize.\n")

print(str(report_path))
PY

python3 "$tmp_script" "$documents_dir" "$report" "$json"
