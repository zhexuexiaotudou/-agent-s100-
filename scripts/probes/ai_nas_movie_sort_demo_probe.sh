#!/usr/bin/env bash
set -euo pipefail

demo_root="${1:-/mnt/nas/openclaw/demo/ai-nas-movie-sort}"
report_root="${2:-/mnt/nas/openclaw/reports/teacher-demos/ai-nas-movie-sort}"

case "$demo_root" in
  ""|"/"|"/tmp"|"/mnt"|"/mnt/nas"|"/mnt/nas/openclaw"|"/root"|"/root/.openclaw"|"/root/.openclaw/workspace") ;;
  /tmp/*|/mnt/nas/openclaw/demo/ai-nas-movie-sort|/mnt/nas/openclaw/demo/ai-nas-movie-sort/*|/root/.openclaw/workspace/demo/ai-nas-movie-sort|/root/.openclaw/workspace/demo/ai-nas-movie-sort/*) safe_demo_root=1 ;;
  *)
    echo "Refusing demo root outside approved AI NAS movie-sort demo directories: $demo_root" >&2
    exit 2
    ;;
esac

if [[ "${safe_demo_root:-0}" != "1" ]]; then
  echo "Refusing unsafe demo root: $demo_root" >&2
  exit 2
fi

case "$report_root" in
  ""|"/"|"/tmp"|"/mnt"|"/mnt/nas"|"/mnt/nas/openclaw"|"/root"|"/root/.openclaw"|"/root/.openclaw/workspace") ;;
  /tmp/*|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports/*) safe_report_root=1 ;;
  *)
    echo "Refusing report root outside approved demo report directories: $report_root" >&2
    exit 2
    ;;
esac

if [[ "${safe_report_root:-0}" != "1" ]]; then
  echo "Refusing unsafe report root: $report_root" >&2
  exit 2
fi

stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/movie_sort_demo_$stamp"
mkdir -p "$run_dir"

python3 - "$demo_root" "$run_dir" <<'PY'
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

demo_root = Path(sys.argv[1])
run_dir = Path(sys.argv[2])
inbox_dir = demo_root / "inbox"
library_dir = demo_root / "library"
report_dir = run_dir
inbox_dir.mkdir(parents=True, exist_ok=True)
library_dir.mkdir(parents=True, exist_ok=True)
report_dir.mkdir(parents=True, exist_ok=True)

samples = {
    "Interstellar.2014.Sci-Fi.movie.txt": "demo placeholder: science fiction movie\n",
    "The.Matrix.1999.Sci-Fi.movie.txt": "demo placeholder: science fiction movie\n",
    "Toy.Story.1995.Animation.movie.txt": "demo placeholder: animation movie\n",
    "Inception.2010.Thriller.movie.txt": "demo placeholder: thriller movie\n",
    "Planet.Earth.2006.Documentary.movie.txt": "demo placeholder: documentary movie\n",
    "Family.Home.Video.2026.Unclassified.movie.txt": "demo placeholder: unclassified home video\n",
}

seeded = []
if not any(path.is_file() for path in inbox_dir.iterdir()):
    for name, text in samples.items():
        path = inbox_dir / name
        path.write_text(text, encoding="utf-8")
        seeded.append(str(path))

rules = [
    ("Sci-Fi", [r"sci[-_. ]?fi", r"science[-_. ]?fiction", r"matrix", r"interstellar"]),
    ("Animation", [r"animation", r"cartoon", r"toy[-_. ]?story"]),
    ("Documentary", [r"documentary", r"docu", r"planet[-_. ]?earth"]),
    ("Thriller", [r"thriller", r"suspense", r"inception"]),
    ("Action", [r"action"]),
    ("Comedy", [r"comedy"]),
    ("Drama", [r"drama"]),
]

def classify(path: Path) -> str:
    text = path.name.lower()
    for label, patterns in rules:
        for pattern in patterns:
            if re.search(pattern, text):
                return label
    return "Unclassified"

def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

records = []
for source in sorted(path for path in inbox_dir.iterdir() if path.is_file()):
    genre = classify(source)
    target_dir = library_dir / genre
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / source.name
    shutil.copy2(source, target)
    record = {
        "source": str(source),
        "target": str(target),
        "type": genre,
        "size_bytes": source.stat().st_size,
        "sha256": sha256(source),
    }
    sidecar = target.with_suffix(target.suffix + ".movie.json")
    sidecar.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    records.append(record)

types = sorted({record["type"] for record in records})
for genre in types:
    manifest = library_dir / genre / "MANIFEST.md"
    lines = [f"# {genre} Movies", ""]
    for record in records:
        if record["type"] == genre:
            lines.append(f"- `{Path(record['target']).name}` from `{record['source']}`")
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_ai_nas_movie_sort_demo_probe",
    "demo_id": "ai_nas_movie_sort_demo",
    "demo_root": str(demo_root),
    "inbox_dir": str(inbox_dir),
    "library_dir": str(library_dir),
    "report_dir": str(report_dir),
    "classification_engine": "deterministic_filename_metadata_rules",
    "seeded_sample_files": seeded,
    "processed_file_count": len(records),
    "classified_file_count": len(records),
    "types": types,
    "originals_preserved": True,
    "copy_mode": "copy2_into_demo_library",
    "scope": {
        "nas_writes": "bounded_to_demo_root_and_report_root",
        "real_media_library_touched": False,
        "external_api_called": False,
        "model_inference_run": False,
        "ros2_or_robot_scope": "out_of_scope",
    },
    "records": records,
}

json_path = report_dir / "movie_sort_demo.json"
md_path = report_dir / "movie_sort_demo.md"
json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

lines = [
    "# AI NAS Movie Sort Demo Evidence",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- demo_root: `{payload['demo_root']}`",
    f"- inbox_dir: `{payload['inbox_dir']}`",
    f"- library_dir: `{payload['library_dir']}`",
    f"- classification_engine: `{payload['classification_engine']}`",
    f"- processed_file_count: `{payload['processed_file_count']}`",
    f"- types: `{', '.join(payload['types'])}`",
    "",
    "## Scope",
    "",
]
for key, value in payload["scope"].items():
    lines.append(f"- `{key}`: `{value}`")
lines.extend(["", "## Sorted Records", ""])
for record in records:
    lines.append(f"- `{Path(record['source']).name}` -> `{record['type']}` -> `{record['target']}`")
lines.extend([
    "",
    "## Recording Script",
    "",
    "1. Show the NAS demo inbox under `/mnt/nas/openclaw/demo/ai-nas-movie-sort/inbox`.",
    "2. Ask OpenClaw on S100P to run `scripts/run_allowlisted_tool.sh ai_nas_movie_sort_demo_probe`.",
    "3. Show the generated `library/<type>/` directories and `movie_sort_demo.md` report on NAS.",
    "4. Point out that originals are preserved and all writes stay inside the approved demo root.",
])
md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(md_path)
PY
