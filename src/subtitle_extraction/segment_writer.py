from __future__ import annotations

from pathlib import Path


def format_ts(seconds: float, *, vtt: bool = False) -> str:
    millis = int(round((seconds - int(seconds)) * 1000))
    total = int(seconds)
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    sep = "." if vtt else ","
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{millis:03d}"


def write_srt(path: str | Path, segments: list[dict]) -> None:
    lines = []
    for idx, seg in enumerate(segments, 1):
        lines.extend(
            [
                str(idx),
                f"{format_ts(float(seg['start_sec']))} --> {format_ts(float(seg['end_sec']))}",
                str(seg["text_redacted"]),
                "",
            ]
        )
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def write_vtt(path: str | Path, segments: list[dict]) -> None:
    lines = ["WEBVTT", ""]
    for seg in segments:
        lines.extend(
            [
                f"{format_ts(float(seg['start_sec']), vtt=True)} --> {format_ts(float(seg['end_sec']), vtt=True)}",
                str(seg["text_redacted"]),
                "",
            ]
        )
    Path(path).write_text("\n".join(lines), encoding="utf-8")
