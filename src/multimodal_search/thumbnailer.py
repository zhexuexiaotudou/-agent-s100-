from __future__ import annotations

from pathlib import Path

try:
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None  # type: ignore[assignment]


def generate_thumbnail(image_path: str | Path, cache_dir: str | Path, asset_id: str) -> dict:
    if Image is None:
        return {"ok": False, "reason": "pillow_unavailable"}
    out_dir = Path(cache_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{asset_id}.jpg"
    with Image.open(image_path) as image:
        rgb = image.convert("RGB")
        rgb.thumbnail((256, 256))
        rgb.save(out, format="JPEG", quality=82)
        width, height = rgb.size
    return {"ok": True, "thumbnail_path": str(out), "width": width, "height": height}
