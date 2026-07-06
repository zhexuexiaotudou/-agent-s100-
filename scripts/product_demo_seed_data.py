#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import wave
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Create synthetic Digua AI Space demo fixtures.")
    parser.add_argument("--root", type=Path, default=Path("demo_data"))
    args = parser.parse_args()
    root = args.root
    for name in ["photos", "videos", "audio", "documents", "movies", "music"]:
        (root / name).mkdir(parents=True, exist_ok=True)
    create_images(root / "photos")
    create_audio(root / "audio" / "meeting_note.wav")
    (root / "documents" / "contract_sample.txt").write_text("Contract sample. Payment and delivery terms.\n", encoding="utf-8")
    (root / "documents" / "invoice_sample.txt").write_text("Invoice sample. Amount 128.00.\n", encoding="utf-8")
    (root / "documents" / "course_note.txt").write_text("Course note sample. Assignment and lesson.\n", encoding="utf-8")
    (root / "movies" / "Example.Movie.2024.mp4").write_bytes(b"synthetic movie placeholder\n")
    (root / "music" / "sample_song.mp3").write_bytes(b"synthetic music placeholder\n")
    manifest = {
        "ok": True,
        "fixture_only_for_ci": True,
        "production_demo_requires_real_user_assets": True,
        "root": str(root),
    }
    (root / "DEMO_FIXTURE_MANIFEST.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(root / "DEMO_FIXTURE_MANIFEST.json")
    return 0


def create_images(out: Path) -> None:
    try:
        from PIL import Image, ImageDraw
    except Exception:
        return
    specs = [
        ("white_shirt_person.jpg", (245, 245, 235), (40, 80, 180), "person white shirt"),
        ("red_shirt_person.jpg", (210, 40, 40), (40, 80, 180), "person red shirt"),
        ("cat_indoor.jpg", (180, 120, 80), (230, 230, 210), "cat indoor"),
        ("dog_grass.jpg", (160, 120, 70), (80, 150, 70), "dog grass"),
        ("car_street.jpg", (80, 120, 200), (160, 160, 160), "car street"),
        ("laptop_desk.jpg", (230, 230, 230), (50, 50, 60), "laptop desk"),
        ("invoice_photo.jpg", (250, 250, 250), (30, 30, 30), "invoice"),
        ("mountain_grass.jpg", (70, 140, 85), (90, 120, 180), "mountain grass"),
    ]
    for filename, primary, secondary, label in specs:
        image = Image.new("RGB", (640, 420), (238, 242, 246))
        draw = ImageDraw.Draw(image)
        draw.rectangle((40, 40, 600, 380), fill=(255, 255, 255), outline=(180, 190, 200))
        draw.ellipse((250, 80, 390, 220), fill=(210, 170, 135))
        draw.rectangle((220, 210, 420, 340), fill=primary)
        draw.rectangle((430, 250, 560, 330), fill=secondary)
        draw.text((60, 60), label, fill=(20, 30, 40))
        image.save(out / filename, quality=90)


def create_audio(path: Path) -> None:
    rate = 16000
    duration = 1.0
    frames = int(rate * duration)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        for i in range(frames):
            sample = int(9000 * math.sin(2 * math.pi * 440 * i / rate))
            wf.writeframesraw(sample.to_bytes(2, "little", signed=True))


if __name__ == "__main__":
    raise SystemExit(main())
