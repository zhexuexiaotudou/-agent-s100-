from __future__ import annotations

from pathlib import Path


def unique_target_rel(personal_root: Path, target_rel: str, reserved: set[str]) -> str:
    normalized = target_rel.replace("\\", "/").strip("/")
    candidate = normalized
    path = Path(normalized)
    stem = path.stem
    suffix = path.suffix
    parent = path.parent.as_posix()
    counter = 1
    while candidate in reserved or (personal_root / candidate).exists():
        filename = f"{stem}_{counter:03d}{suffix}"
        candidate = f"{parent}/{filename}" if parent not in {"", "."} else filename
        counter += 1
    reserved.add(candidate)
    return candidate
