from __future__ import annotations


def symbolic_summary(*, modality: str, labels: list[str], ocr_status: str, transcript_status: str) -> str:
    if modality == "image":
        label_text = ", ".join(labels[:5]) if labels else "no local object labels"
        return f"Local indexed photo. Detected: {label_text}. OCR status: {ocr_status}. Summary is symbolic, not VLM caption."
    if modality == "video":
        label_text = ", ".join(labels[:5]) if labels else "no local object labels"
        return f"Local indexed video. Keyframe labels: {label_text}. Transcript status: {transcript_status}."
    if modality == "audio":
        return f"Local indexed audio. Transcript status: {transcript_status}."
    if modality == "document":
        return f"Local indexed document. OCR/text status: {ocr_status}."
    return f"Local indexed {modality or 'asset'}."
