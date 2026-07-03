#!/usr/bin/env bash
set -euo pipefail

input_dir="${1:-/root/.openclaw/workspace/photos}"
report_dir="${2:-/root/.openclaw/workspace/reports/image-captions}"

case "$input_dir" in
  /tmp/*|/mnt/nas/openclaw/photos|/mnt/nas/openclaw/photos/*|/root/.openclaw/workspace/photos|/root/.openclaw/workspace/photos/*) ;;
  *)
    echo "Refusing input path outside approved photo directories: $input_dir" >&2
    exit 2
    ;;
esac

case "$report_dir" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_dir" >&2
    exit 2
    ;;
esac

mkdir -p "$report_dir"
stamp="$(date +%Y%m%d-%H%M%S)"
report="$report_dir/image_caption_index_$stamp.md"
jsonl="$report_dir/image_caption_index_$stamp.jsonl"

tmp_script="$(mktemp)"
trap 'rm -f "$tmp_script"' EXIT

cat > "$tmp_script" <<'PY'
import hashlib
import json
import os
import re
import struct
import sys
from pathlib import Path

input_dir = Path(sys.argv[1])
jsonl_path = Path(sys.argv[2])

allowed_ext = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}


def slug_words(path: Path) -> str:
    parts = list(path.parts[-4:])
    stem = path.stem
    raw = " ".join(parts[:-1] + [stem])
    raw = re.sub(r"[_\-]+", " ", raw)
    raw = re.sub(r"\s+", " ", raw).strip()
    return raw or path.name


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def png_dimensions(data: bytes):
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        return struct.unpack(">II", data[16:24])
    return None


def gif_dimensions(data: bytes):
    if (data.startswith(b"GIF87a") or data.startswith(b"GIF89a")) and len(data) >= 10:
        return struct.unpack("<HH", data[6:10])
    return None


def jpeg_dimensions(path: Path):
    with path.open("rb") as fh:
        data = fh.read(2)
        if data != b"\xff\xd8":
            return None
        while True:
            marker_start = fh.read(1)
            if not marker_start:
                return None
            if marker_start != b"\xff":
                continue
            marker = fh.read(1)
            while marker == b"\xff":
                marker = fh.read(1)
            if marker in {b"\xd8", b"\xd9"}:
                continue
            length_bytes = fh.read(2)
            if len(length_bytes) != 2:
                return None
            length = struct.unpack(">H", length_bytes)[0]
            if length < 2:
                return None
            if marker and marker[0] in list(range(0xC0, 0xC4)) + list(range(0xC5, 0xC8)) + list(range(0xC9, 0xCC)) + list(range(0xCD, 0xD0)):
                payload = fh.read(length - 2)
                if len(payload) >= 5:
                    height, width = struct.unpack(">HH", payload[1:5])
                    return width, height
                return None
            fh.seek(length - 2, os.SEEK_CUR)


def webp_dimensions(data: bytes):
    if not (data.startswith(b"RIFF") and data[8:12] == b"WEBP") or len(data) < 30:
        return None
    chunk = data[12:16]
    if chunk == b"VP8 " and len(data) >= 30:
        width = struct.unpack("<H", data[26:28])[0] & 0x3FFF
        height = struct.unpack("<H", data[28:30])[0] & 0x3FFF
        return width, height
    if chunk == b"VP8L" and len(data) >= 25:
        b0, b1, b2, b3 = data[21:25]
        width = 1 + (((b1 & 0x3F) << 8) | b0)
        height = 1 + (((b3 & 0xF) << 10) | (b2 << 2) | ((b1 & 0xC0) >> 6))
        return width, height
    if chunk == b"VP8X" and len(data) >= 30:
        width = 1 + int.from_bytes(data[24:27], "little")
        height = 1 + int.from_bytes(data[27:30], "little")
        return width, height
    return None


def dimensions(path: Path):
    try:
        with path.open("rb") as fh:
            data = fh.read(64)
        ext = path.suffix.lower()
        if ext == ".png":
            return png_dimensions(data)
        if ext == ".gif":
            return gif_dimensions(data)
        if ext in {".jpg", ".jpeg"}:
            return jpeg_dimensions(path)
        if ext == ".webp":
            return webp_dimensions(data)
    except Exception:
        return None
    return None


records = []
if input_dir.exists():
    for path in sorted(input_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in allowed_ext:
            continue
        rel = path.relative_to(input_dir)
        dims = dimensions(path)
        width, height = dims if dims else (None, None)
        size = path.stat().st_size
        caption = f"Image file {slug_words(rel)}"
        if width and height:
            caption += f", {width}x{height}px"
        record = {
            "path": str(path),
            "relative_path": str(rel),
            "caption": caption,
            "width": width,
            "height": height,
            "bytes": size,
            "sha256": sha256_file(path),
            "mtime": int(path.stat().st_mtime),
        }
        records.append(record)

with jsonl_path.open("w", encoding="utf-8") as out:
    for record in records:
        out.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

print(json.dumps({"count": len(records), "jsonl": str(jsonl_path)}, sort_keys=True))
PY

summary="$(python3 "$tmp_script" "$input_dir" "$jsonl")"
count="$(printf '%s\n' "$summary" | sed -E 's/.*"count": ([0-9]+).*/\1/')"

{
  echo "# Image Caption Index"
  echo
  echo "- generated_at: $(date -Is)"
  echo "- input_dir: $input_dir"
  echo "- report: $report"
  echo "- jsonl: $jsonl"
  echo "- mode: deterministic metadata captions; semantic vision captions are pending"
  echo
  echo "## Summary"
  echo
  echo "| Check | Value |"
  echo "| --- | --- |"
  echo "| Image records | $count |"
  echo "| JSONL index | $jsonl |"
  echo
  echo "## Caption Records"
  echo
  if [[ "$count" == "0" ]]; then
    echo
    echo "No supported image files found."
  else
    echo
    echo "| Relative path | Caption | Size | Dimensions | SHA256 |"
    echo "| --- | --- | ---: | --- | --- |"
    python3 - "$jsonl" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as fh:
    for line in fh:
        record = json.loads(line)
        dims = "unknown"
        if record.get("width") and record.get("height"):
            dims = f"{record['width']}x{record['height']}"
        print(f"| `{record['relative_path']}` | {record['caption']} | {record['bytes']} | {dims} | `{record['sha256'][:16]}` |")
PY
  fi
  echo
  echo "## Search Usage"
  echo
  echo "- Search the Markdown table for a human-readable quick check."
  echo "- Use the JSONL file for future vector indexing or semantic caption replacement."
  echo "- B-003 is not complete until NAS-backed photos are indexed and semantic captions are added or explicitly scoped out."
} > "$report"

echo "$report"
