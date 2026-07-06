from __future__ import annotations

from pathlib import Path


ALLOWED_COLORS = {"white", "black", "red", "blue", "green", "yellow", "gray", "unknown"}


def classify_rgb(rgb: tuple[float, float, float]) -> str:
    r, g, b = rgb
    mx = max(r, g, b)
    mn = min(r, g, b)
    avg = (r + g + b) / 3.0
    if avg >= 210 and mx - mn <= 45:
        return "white"
    if avg <= 55:
        return "black"
    if mx - mn <= 30:
        return "gray"
    if r >= 135 and r >= g * 1.25 and r >= b * 1.25:
        return "red"
    if b >= 120 and b >= r * 1.2 and b >= g * 1.05:
        return "blue"
    if g >= 115 and g >= r * 1.15 and g >= b * 1.15:
        return "green"
    if r >= 135 and g >= 120 and b <= 110:
        return "yellow"
    return "unknown"


def crop_mean_color(image_path: str | Path, bbox: tuple[float, float, float, float], *, part: str) -> str:
    try:
        from PIL import Image
    except Exception:
        return "unknown"
    try:
        with Image.open(image_path) as image:
            rgb = image.convert("RGB")
            width, height = rgb.size
            x1, y1, x2, y2 = bbox
            left = max(0, min(width - 1, int(x1 * width)))
            right = max(left + 1, min(width, int(x2 * width)))
            top = max(0, min(height - 1, int(y1 * height)))
            bottom = max(top + 1, min(height, int(y2 * height)))
            mid = top + max(1, (bottom - top) // 2)
            if part == "upper":
                bottom = mid
            elif part == "lower":
                top = mid
            if right - left < 4 or bottom - top < 4:
                return "unknown"
            region = rgb.crop((left, top, right, bottom)).resize((1, 1))
            return classify_rgb(tuple(float(v) for v in region.getpixel((0, 0))))
    except Exception:
        return "unknown"
