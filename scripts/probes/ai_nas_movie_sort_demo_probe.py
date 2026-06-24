#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
import re
import shutil
from datetime import datetime
from pathlib import Path

from ai_nas_common import safe_write_json, safe_write_text


TOOL_ID = "ai_nas_movie_sort_demo_probe"
DEFAULT_DEMO_ROOT = Path("/mnt/nas/openclaw/demo/ai-nas-movie-sort")
DEFAULT_REPORT_ROOT = Path("/mnt/nas/openclaw/reports/teacher-demos/ai-nas-movie-sort")
SAMPLES = {
    "Interstellar.2014.Sci-Fi.movie.txt": "demo placeholder: science fiction movie\n",
    "The.Matrix.1999.Sci-Fi.movie.txt": "demo placeholder: science fiction movie\n",
    "Toy.Story.1995.Animation.movie.txt": "demo placeholder: animation movie\n",
    "Inception.2010.Thriller.movie.txt": "demo placeholder: thriller movie\n",
    "Planet.Earth.2006.Documentary.movie.txt": "demo placeholder: documentary movie\n",
    "Family.Home.Video.2026.Unclassified.movie.txt": "demo placeholder: unclassified home video\n",
}
RULES = [
    ("Sci-Fi", [r"sci[-_. ]?fi", r"science[-_. ]?fiction", r"matrix", r"interstellar"]),
    ("Animation", [r"animation", r"cartoon", r"toy[-_. ]?story"]),
    ("Documentary", [r"documentary", r"docu", r"planet[-_. ]?earth"]),
    ("Thriller", [r"thriller", r"suspense", r"inception"]),
    ("Action", [r"action"]),
    ("Comedy", [r"comedy"]),
    ("Drama", [r"drama"]),
]


def is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        return False


def is_safe_demo_root(path: Path) -> bool:
    resolved = path.resolve()
    allowed = [
        Path("/tmp"),
        Path(tempfile.gettempdir()),
        Path("/mnt/nas/openclaw/demo/ai-nas-movie-sort"),
        Path("/root/.openclaw/workspace/demo/ai-nas-movie-sort"),
    ]
    return any(resolved == root or is_relative_to(resolved, root) for root in allowed)


def is_safe_report_root(path: Path) -> bool:
    resolved = path.resolve()
    allowed = [
        Path("/tmp"),
        Path(tempfile.gettempdir()),
        Path("/mnt/nas/openclaw/reports"),
        Path("/root/.openclaw/workspace/reports"),
    ]
    return any(resolved == root or is_relative_to(resolved, root) for root in allowed)


def classify(path: Path) -> str:
    text = path.name.lower()
    for label, patterns in RULES:
        if any(re.search(pattern, text) for pattern in patterns):
            return label
    return "Unclassified"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def seed_inbox(inbox_dir: Path) -> list[str]:
    inbox_dir.mkdir(parents=True, exist_ok=True)
    if any(path.is_file() for path in inbox_dir.iterdir()):
        return []
    seeded = []
    for name, text in SAMPLES.items():
        path = inbox_dir / name
        path.write_text(text, encoding="utf-8")
        seeded.append(str(path))
    return seeded


def run_demo(demo_root: Path, report_root: Path) -> tuple[dict, Path, Path]:
    if not is_safe_demo_root(demo_root):
        raise ValueError(f"Refusing demo root outside approved AI NAS movie-sort demo directories: {demo_root}")
    if not is_safe_report_root(report_root):
        raise ValueError(f"Refusing report root outside approved demo report directories: {report_root}")
    stamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    run_dir = report_root / f"movie_sort_demo_{stamp}"
    inbox_dir = demo_root / "inbox"
    library_dir = demo_root / "library"
    run_dir.mkdir(parents=True, exist_ok=True)
    library_dir.mkdir(parents=True, exist_ok=True)
    seeded = seed_inbox(inbox_dir)
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
            "sha256": sha256_file(source),
        }
        safe_write_json(target.with_suffix(target.suffix + ".movie.json"), record)
        records.append(record)
    types = sorted({record["type"] for record in records})
    for genre in types:
        manifest = library_dir / genre / "MANIFEST.md"
        lines = [f"# {genre} Movies", ""]
        for record in records:
            if record["type"] == genre:
                lines.append(f"- `{Path(record['target']).name}` from `{record['source']}`")
        safe_write_text(manifest, "\n".join(lines) + "\n")
    payload = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "tool_id": TOOL_ID,
        "verdict": "ok_ai_nas_movie_sort_demo_probe",
        "demo_id": "ai_nas_movie_sort_demo",
        "demo_root": str(demo_root),
        "inbox_dir": str(inbox_dir),
        "library_dir": str(library_dir),
        "report_dir": str(run_dir),
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
        "audit": {
            "tool_id": TOOL_ID,
            "source_files_modified": False,
            "personal_source_modified": False,
            "delete_performed": False,
            "move_performed": False,
            "overwrite_performed": False,
            "writes": "bounded demo files and Markdown/JSON reports under approved demo/report prefixes",
        },
    }
    json_path = run_dir / "movie_sort_demo.json"
    md_path = run_dir / "movie_sort_demo.md"
    safe_write_json(json_path, payload)
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
    lines.extend(
        [
            "",
            "## Recording Script",
            "",
            "1. Show the NAS demo inbox under `/mnt/nas/openclaw/demo/ai-nas-movie-sort/inbox`.",
            "2. Ask OpenClaw on S100P to run `scripts/run_allowlisted_tool.sh ai_nas_movie_sort_demo_probe`.",
            "3. Show the generated `library/<type>/` directories and `movie_sort_demo.md` report on NAS.",
            "4. Point out that originals are preserved and all writes stay inside the approved demo root.",
        ]
    )
    safe_write_text(md_path, "\n".join(lines) + "\n")
    return payload, md_path, json_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Bounded AI-NAS movie-sort demo evidence probe.")
    parser.add_argument("demo_root", nargs="?", type=Path, default=DEFAULT_DEMO_ROOT)
    parser.add_argument("report_root", nargs="?", type=Path, default=DEFAULT_REPORT_ROOT)
    args = parser.parse_args()
    _payload, md_path, json_path = run_demo(args.demo_root, args.report_root)
    print(md_path)
    print(json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
