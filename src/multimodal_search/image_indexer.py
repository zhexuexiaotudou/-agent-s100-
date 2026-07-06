from __future__ import annotations

from pathlib import Path

try:
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None  # type: ignore[assignment]


def image_metadata(path: str | Path) -> dict:
    if Image is None:
        return {"width": None, "height": None, "codec": Path(path).suffix.lower().lstrip(".") or "unknown"}
    try:
        with Image.open(path) as image:
            return {"width": int(image.width), "height": int(image.height), "codec": image.format or Path(path).suffix.lower().lstrip(".")}
    except Exception as exc:
        return {
            "width": None,
            "height": None,
            "codec": Path(path).suffix.lower().lstrip(".") or "unknown",
            "metadata_mode": "unreadable_image",
            "error": f"{type(exc).__name__}:{exc}",
        }
