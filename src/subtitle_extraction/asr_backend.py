from __future__ import annotations

import os
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Any

import numpy as np


class LocalAsrBackend:
    def __init__(self) -> None:
        self.backend = os.environ.get("DIGUA_ASR_BACKEND", "fixture").strip().lower() or "fixture"
        self.model_dir = os.environ.get("DIGUA_ASR_MODEL_DIR")
        self.device = os.environ.get("DIGUA_ASR_DEVICE", "cpu")
        self.require_real = os.environ.get("DIGUA_ASR_REQUIRE_REAL", "1").lower() in {"1", "true", "yes"}

    def status(self) -> dict[str, Any]:
        available = False
        reason = None
        model_name = Path(self.model_dir).name if self.model_dir else self.backend
        if self.backend == "fixture":
            available = not self.require_real
            reason = "fixture_backend_not_allowed_for_product_gate" if self.require_real else None
        elif self.backend == "faster_whisper":
            try:
                import faster_whisper  # noqa: F401

                available = bool(self.model_dir and Path(self.model_dir).exists())
                reason = None if available else "asr_model_dir_missing"
            except Exception as exc:
                reason = f"faster_whisper_unavailable:{type(exc).__name__}"
        elif self.backend == "vosk":
            try:
                import vosk  # noqa: F401

                available = bool(self.model_dir and Path(self.model_dir).exists())
                reason = None if available else "asr_model_dir_missing"
            except Exception as exc:
                reason = f"vosk_unavailable:{type(exc).__name__}"
        elif self.backend == "whisper_cpp":
            available = bool(self.model_dir and Path(self.model_dir).exists())
            reason = None if available else "whisper_cpp_model_missing"
        elif self.backend == "transformers_whisper":
            try:
                from transformers import WhisperForConditionalGeneration, WhisperProcessor  # noqa: F401

                available = bool(self.model_dir and Path(self.model_dir).exists())
                reason = None if available else "asr_model_dir_missing"
            except Exception as exc:
                reason = f"transformers_whisper_unavailable:{type(exc).__name__}"
        else:
            reason = "unsupported_asr_backend"
        return {
            "ok": True,
            "backend": self.backend,
            "model_name": model_name,
            "model_dir_configured": bool(self.model_dir),
            "device": self.device,
            "available": available,
            "real_asr": available and self.backend != "fixture",
            "cloud_used": False,
            "local_only": True,
            "degraded": not available or self.backend == "fixture",
            "degraded_reason": reason,
        }

    def transcribe(self, media_path: str | Path) -> dict[str, Any]:
        status = self.status()
        if not status["available"]:
            return {"ok": False, "error": status.get("degraded_reason") or "asr_backend_unavailable", "status": status}
        if self.backend == "fixture":
            text = "fixture transcript for local CI only"
            return {
                "ok": True,
                "language": "en",
                "duration_sec": 3.0,
                "segments": [{"start_sec": 0.0, "end_sec": 3.0, "text_redacted": text, "confidence": 1.0}],
                "backend": self.backend,
                "model_name": status["model_name"],
                "fixture_only_for_ci": True,
            }
        if self.backend == "transformers_whisper":
            return self._transcribe_transformers_whisper(media_path)
        return {"ok": False, "error": "real_asr_execution_not_implemented_for_backend", "status": status}

    def _transcribe_transformers_whisper(self, media_path: str | Path) -> dict[str, Any]:
        status = self.status()
        if not status["available"] or not self.model_dir:
            return {"ok": False, "error": status.get("degraded_reason") or "asr_backend_unavailable", "status": status}
        from transformers import WhisperForConditionalGeneration, WhisperProcessor

        wav_path: Path | None = None
        cleanup = False
        source = Path(media_path)
        if source.suffix.lower() == ".wav":
            wav_path = source
        else:
            tmp = tempfile.NamedTemporaryFile(prefix="digua_asr_", suffix=".wav", delete=False)
            tmp.close()
            wav_path = Path(tmp.name)
            cleanup = True
            cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(source), "-ac", "1", "-ar", "16000", str(wav_path)]
            completed = subprocess.run(cmd, text=True, capture_output=True, check=False, timeout=120)
            if completed.returncode != 0:
                return {"ok": False, "error": "ffmpeg_audio_extract_failed", "stderr": (completed.stderr or "")[-500:], "status": status}
        try:
            audio = _read_wav_mono_16k(wav_path)
            processor = WhisperProcessor.from_pretrained(self.model_dir, local_files_only=True)
            model = WhisperForConditionalGeneration.from_pretrained(self.model_dir, local_files_only=True)
            model.eval()
            inputs = processor(audio, sampling_rate=16000, return_tensors="pt")
            import torch

            with torch.no_grad():
                generated_ids = model.generate(inputs["input_features"], max_new_tokens=96)
            text = processor.batch_decode(generated_ids, skip_special_tokens=True)[0].strip() or "[no speech detected]"
            duration = float(len(audio) / 16000.0)
            return {
                "ok": True,
                "language": "unknown",
                "duration_sec": duration,
                "segments": [{"start_sec": 0.0, "end_sec": max(duration, 0.1), "text_redacted": text[:1000], "confidence": None}],
                "backend": self.backend,
                "model_name": Path(self.model_dir).name,
                "fixture_only_for_ci": False,
            }
        finally:
            if cleanup and wav_path is not None:
                try:
                    wav_path.unlink()
                except OSError:
                    pass


def _read_wav_mono_16k(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as wf:
        channels = wf.getnchannels()
        sample_width = wf.getsampwidth()
        rate = wf.getframerate()
        frames = wf.readframes(wf.getnframes())
    if sample_width != 2:
        raise RuntimeError("only_16bit_wav_supported")
    data = np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0
    if channels > 1:
        data = data.reshape(-1, channels).mean(axis=1)
    if rate != 16000:
        raise RuntimeError(f"wav_rate_must_be_16000:{rate}")
    return data
