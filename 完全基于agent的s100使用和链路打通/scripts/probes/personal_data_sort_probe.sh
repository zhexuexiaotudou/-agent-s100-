#!/usr/bin/env bash
set -euo pipefail

share_name="${1:-Personal}"
source_root="${2:-/}"
sorted_root="${3:-Sorted}"
report_root="${4:-/mnt/nas/openclaw/reports/personal-data-sort}"
max_files="${PERSONAL_DATA_SORT_MAX_FILES:-500}"
max_bytes="${PERSONAL_DATA_SORT_MAX_BYTES:-1073741824}"
nas_host="${PERSONAL_DATA_SORT_NAS_HOST:-169.254.143.37}"
credentials_file="${PERSONAL_DATA_SORT_SMB_CREDENTIALS:-/root/.smbcredentials-openclaw}"
dry_run="${PERSONAL_DATA_SORT_DRY_RUN:-0}"

case "$share_name" in
  Personal) ;;
  *)
    echo "Refusing SMB share outside approved Personal share: $share_name" >&2
    exit 2
    ;;
esac

case "$source_root" in
  ""|"/"|Movies|Movies/*|Documents|Documents/*|Photos|Photos/*|Datasets|Datasets/*|Inbox|Inbox/*) ;;
  *)
    echo "Refusing source root outside approved Personal subtrees: $source_root" >&2
    exit 2
    ;;
esac

case "$sorted_root" in
  Sorted|Sorted/*) ;;
  *)
    echo "Refusing sorted root outside Personal/Sorted: $sorted_root" >&2
    exit 2
    ;;
esac

case "$report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing report root outside approved report directories: $report_root" >&2
    exit 2
    ;;
esac

if ! command -v smbclient >/dev/null 2>&1; then
  echo "Missing smbclient on S100P" >&2
  exit 3
fi
case "$dry_run" in
  0|1) ;;
  *)
    echo "PERSONAL_DATA_SORT_DRY_RUN must be 0 or 1." >&2
    exit 2
    ;;
esac
if ! sudo test -f "$credentials_file"; then
  echo "Missing SMB credentials file: $credentials_file" >&2
  exit 4
fi

stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/personal_data_sort_$stamp"
work_dir="/tmp/personal_data_sort_$stamp"
download_dir="$work_dir/download"
upload_plan="$work_dir/upload_commands.smb"
mkdir -p "$run_dir" "$download_dir"

python3 - "$share_name" "$source_root" "$sorted_root" "$run_dir" "$download_dir" "$max_files" "$max_bytes" <<'PY'
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

share_name, source_root, sorted_root, run_dir_text, download_dir_text, max_files_text, max_bytes_text = sys.argv[1:8]
run_dir = Path(run_dir_text)
download_dir = Path(download_dir_text)
max_files = int(max_files_text)
max_bytes = int(max_bytes_text)

source = source_root.strip("/")
source_parts = [part for part in source.split("/") if part]
source_display = "/" + "/".join(source_parts) if source_parts else "/"
download_target = download_dir.joinpath(*source_parts) if source_parts else download_dir
download_target.mkdir(parents=True, exist_ok=True)

fetch_script = run_dir / "fetch_commands.smb"
commands = ["prompt off", "recurse on"]
if source_parts:
    for part in source_parts:
        commands.append(f'cd "{part}"')
commands.append(f'lcd "{download_target}"')
commands.append("mget *")
fetch_script.write_text("\n".join(commands) + "\n", encoding="utf-8")

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "prepared_personal_data_sort_fetch",
    "share_name": share_name,
    "source_root": source_display,
    "sorted_root": sorted_root,
    "run_dir": str(run_dir),
    "download_dir": str(download_dir),
    "download_target": str(download_target),
    "max_files": max_files,
    "max_bytes": max_bytes,
    "fetch_script": str(fetch_script),
}
(run_dir / "personal_data_sort_fetch_plan.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(fetch_script)
PY

fetch_script="$(cat "$run_dir/personal_data_sort_fetch_plan.json" | python3 -c 'import json,sys; print(json.load(sys.stdin)["fetch_script"])')"

sudo smbclient "//$nas_host/$share_name" -A "$credentials_file" -m SMB3 -E -b 65536 < "$fetch_script" > "$run_dir/smb_fetch.stdout" 2> "$run_dir/smb_fetch.stderr" || {
  echo "SMB fetch failed. See $run_dir/smb_fetch.stderr" >&2
  exit 5
}

python3 - "$share_name" "$source_root" "$sorted_root" "$run_dir" "$download_dir" "$upload_plan" "$max_files" "$max_bytes" "$dry_run" <<'PY'
import hashlib
import json
import mimetypes
import os
import re
import sys
from datetime import datetime
from pathlib import Path

share_name, source_root, sorted_root, run_dir_text, download_dir_text, upload_plan_text, max_files_text, max_bytes_text, dry_run_text = sys.argv[1:10]
run_dir = Path(run_dir_text)
download_dir = Path(download_dir_text)
upload_plan = Path(upload_plan_text)
max_files = int(max_files_text)
max_bytes = int(max_bytes_text)
dry_run = dry_run_text == "1"

skip_top = {"@Recycle", "@Recently-Snapshot", sorted_root.split("/")[0], ".snapshot", "#recycle"}
movie_exts = {".movie", ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".txt"}
doc_exts = {".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".csv", ".md", ".txt"}
photo_exts = {".jpg", ".jpeg", ".png", ".gif", ".heic", ".bmp", ".tif", ".tiff", ".webp"}
audio_exts = {".mp3", ".flac", ".wav", ".aac", ".m4a", ".ogg"}
archive_exts = {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"}

genre_rules = [
    ("Sci-Fi", [r"sci[-_. ]?fi", r"science[-_. ]?fiction", r"interstellar", r"matrix", r"arrival"]),
    ("Animation", [r"animation", r"toy[-_. ]?story", r"spirited[-_. ]?away", r"coco", r"your[-_. ]?name"]),
    ("Documentary", [r"documentary", r"planet[-_. ]?earth", r"free[-_. ]?solo"]),
    ("Thriller", [r"thriller", r"inception"]),
    ("Action", [r"action", r"dark[-_. ]?knight", r"mad[-_. ]?max"]),
    ("Drama", [r"drama", r"parasite", r"forrest[-_. ]?gump", r"shawshank"]),
    ("Crime", [r"crime", r"godfather", r"joker"]),
    ("Mystery", [r"mystery", r"knives[-_. ]?out"]),
    ("Comedy", [r"comedy", r"grand[-_. ]?budapest"]),
    ("Musical", [r"musical", r"la[-_. ]?la[-_. ]?land"]),
]

def quote_smb(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'

def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def genre_for(name: str) -> str:
    lower = name.lower()
    for genre, patterns in genre_rules:
        if any(re.search(pattern, lower) for pattern in patterns):
            return genre
    return "Unclassified"

def category_for(path: Path) -> tuple[str, str]:
    name = path.name
    lower = name.lower()
    ext = path.suffix.lower()
    if lower.endswith(".movie.txt") or ext in {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v"}:
        return ("Movies", genre_for(name))
    if ext in photo_exts:
        return ("Photos", "Images")
    if ext in audio_exts:
        return ("Audio", "Music")
    if ext in archive_exts:
        return ("Archives", "Compressed")
    if ext in doc_exts:
        return ("Documents", ext.lstrip(".").upper() or "Text")
    return ("Other", "Unclassified")

files = []
for path in sorted(download_dir.rglob("*")):
    if not path.is_file():
        continue
    rel = path.relative_to(download_dir)
    if rel.parts and rel.parts[0] in skip_top:
        continue
    if any(part in skip_top for part in rel.parts):
        continue
    files.append(path)

total_bytes = sum(path.stat().st_size for path in files)
errors = []
if len(files) > max_files:
    errors.append(f"file count {len(files)} exceeds max_files {max_files}")
if total_bytes > max_bytes:
    errors.append(f"total bytes {total_bytes} exceeds max_bytes {max_bytes}")

records = []
seen_hashes = {}
used_targets = {}
duplicate_groups = {}
target_conflicts = []
for path in files:
    rel = path.relative_to(download_dir)
    category, subcategory = category_for(path)
    target_dir = f"{sorted_root}/{category}/{subcategory}"
    base_target_path = f"{target_dir}/{path.name}"
    digest = sha256(path)
    target_path = base_target_path
    action = "copy"
    action_reason = "new_sorted_copy"
    if digest in seen_hashes:
        action = "report_duplicate_only"
        action_reason = "same_sha256_seen_in_source"
        duplicate_groups.setdefault(digest, [seen_hashes[digest]]).append(str(rel).replace(os.sep, "/"))
    elif target_path in used_targets:
        stem = path.stem
        suffix = path.suffix
        renamed_name = f"{stem}.{digest[:8]}{suffix}"
        target_path = f"{target_dir}/{renamed_name}"
        target_conflicts.append({
            "original_target": base_target_path,
            "renamed_target": target_path,
            "source_relative_path": str(rel).replace(os.sep, "/"),
            "strategy": "rename_keep_both_no_overwrite",
        })
        action_reason = "target_name_conflict_renamed"
    if action == "copy":
        seen_hashes[digest] = str(rel).replace(os.sep, "/")
        used_targets[target_path] = digest
    record = {
        "source_relative_path": str(rel).replace(os.sep, "/"),
        "target_relative_path": target_path,
        "base_target_relative_path": base_target_path,
        "category": category,
        "subcategory": subcategory,
        "size_bytes": path.stat().st_size,
        "sha256": digest,
        "action": action,
        "action_reason": action_reason,
    }
    records.append(record)

commands = ["prompt off"]
made_dirs = set()
for record, path in zip(records, files):
    if record["action"] != "copy":
        continue
    parts = record["target_relative_path"].split("/")[:-1]
    acc = []
    for part in parts:
        acc.append(part)
        current = "/".join(acc)
        if current not in made_dirs:
            commands.append(f"mkdir {quote_smb(current)}")
            made_dirs.add(current)
    commands.append(f"put {quote_smb(str(path))} {quote_smb(record['target_relative_path'])}")

upload_plan.write_text("\n".join(commands) + "\n", encoding="utf-8")

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "blocked_safety_limits" if errors else "ok_personal_data_sort_probe",
    "share_name": share_name,
    "source_root": source_root,
    "sorted_root": sorted_root,
    "download_dir": str(download_dir),
    "report_dir": str(run_dir),
    "dry_run": dry_run,
    "copy_mode": "dry_run_plan_only_no_upload" if dry_run else "copy_to_personal_sorted_preserve_originals",
    "safety_model": "non_destructive_copy_sort_with_duplicate_report_only",
    "scope_model": "approved_personal_share_and_subtrees_only",
    "conflict_strategy": "rename_keep_both_no_overwrite_for_same_run_target_conflicts",
    "dedupe_strategy": "same_sha256_duplicate_files_are_reported_not_deleted",
    "originals_preserved": True,
    "upload_performed": not dry_run,
    "delete_or_move_performed": False,
    "overwrite_source_performed": False,
    "external_api_called": False,
    "file_count": len(files),
    "copy_count": sum(1 for record in records if record["action"] == "copy"),
    "duplicate_report_only_count": sum(1 for record in records if record["action"] == "report_duplicate_only"),
    "total_bytes": total_bytes,
    "categories": sorted(set(record["category"] for record in records)),
    "subcategories": sorted(set(f"{record['category']}/{record['subcategory']}" for record in records)),
    "duplicate_groups": duplicate_groups,
    "target_conflicts": target_conflicts,
    "upload_plan": str(upload_plan),
    "errors": errors,
    "records": records,
}

json_path = run_dir / "personal_data_sort.json"
md_path = run_dir / "personal_data_sort.md"
json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

lines = [
    "# Personal Data Sort Report",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- share_name: `{share_name}`",
    f"- source_root: `{source_root}`",
    f"- sorted_root: `{sorted_root}`",
    f"- file_count: `{payload['file_count']}`",
    f"- copy_count: `{payload['copy_count']}`",
    f"- duplicate_report_only_count: `{payload['duplicate_report_only_count']}`",
    f"- total_bytes: `{payload['total_bytes']}`",
    f"- copy_mode: `{payload['copy_mode']}`",
    f"- dry_run: `{payload['dry_run']}`",
    f"- upload_performed: `{payload['upload_performed']}`",
    f"- safety_model: `{payload['safety_model']}`",
    f"- conflict_strategy: `{payload['conflict_strategy']}`",
    f"- dedupe_strategy: `{payload['dedupe_strategy']}`",
    f"- originals_preserved: `{payload['originals_preserved']}`",
    f"- delete_or_move_performed: `{payload['delete_or_move_performed']}`",
    f"- overwrite_source_performed: `{payload['overwrite_source_performed']}`",
    "",
    "## Safety Policy",
    "",
    "- The Personal share is treated as the user's personal data library.",
    "- This probe does not move, delete, or rename original files.",
    "- Sorted output is a copied organization view under `Personal/Sorted`.",
    "- In dry-run mode this report only writes the plan and does not upload sorted copies.",
    "- Duplicate files are detected by SHA256 and reported only; no automatic deletion is performed.",
    "- Same-run target filename conflicts are renamed with a short hash to avoid overwrite.",
    "",
    "## Categories",
    "",
]
for item in payload["subcategories"]:
    lines.append(f"- `{item}`")
lines.extend(["", "## Sorted Records", ""])
for record in records:
    lines.append(
        f"- `{record['source_relative_path']}` -> `{record['target_relative_path']}` "
        f"({record['size_bytes']} bytes, action={record['action']}, reason={record['action_reason']})"
    )
if duplicate_groups:
    lines.extend(["", "## Duplicate Groups", ""])
    for digest, members in duplicate_groups.items():
        lines.append(f"- `{digest}`")
        for member in members:
            lines.append(f"  - `{member}`")
if target_conflicts:
    lines.extend(["", "## Target Conflicts", ""])
    for conflict in target_conflicts:
        lines.append(
            f"- `{conflict['source_relative_path']}`: `{conflict['original_target']}` -> "
            f"`{conflict['renamed_target']}` ({conflict['strategy']})"
        )
if errors:
    lines.extend(["", "## Errors", ""])
    for error in errors:
        lines.append(f"- `{error}`")
md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

print(md_path)
if errors:
    raise SystemExit(6)
PY

if [[ "$dry_run" == "1" ]]; then
  printf 'dry_run=1; upload skipped\n' > "$run_dir/smb_upload.stdout"
  : > "$run_dir/smb_upload.stderr"
else
  sudo smbclient "//$nas_host/$share_name" -A "$credentials_file" -m SMB3 -E -b 65536 < "$upload_plan" > "$run_dir/smb_upload.stdout" 2> "$run_dir/smb_upload.stderr" || {
    echo "SMB upload failed. See $run_dir/smb_upload.stderr" >&2
    exit 7
  }
fi

cat "$run_dir/personal_data_sort.md"
