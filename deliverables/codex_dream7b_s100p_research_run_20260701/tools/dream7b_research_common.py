#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import platform
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np


VOCAB_SIZE = 152064
SEQ_LEN = 128
HIDDEN_SIZE = 3584
MASK_TOKEN_ID = 151666


def now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def json_default(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, Path):
        return str(value)
    return str(value)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=json_default) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_cmd(args: list[str], timeout: int = 300, cwd: Path | None = None) -> dict[str, Any]:
    started = datetime.now(timezone.utc)
    try:
        proc = subprocess.run(args, text=True, capture_output=True, timeout=timeout, cwd=str(cwd) if cwd else None)
        return {
            "args": args,
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "started_at_utc": started.isoformat(),
            "ended_at_utc": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:
        return {
            "args": args,
            "returncode": None,
            "stdout": "",
            "stderr": f"{type(exc).__name__}: {exc}",
            "started_at_utc": started.isoformat(),
            "ended_at_utc": datetime.now(timezone.utc).isoformat(),
        }


def host_metadata() -> dict[str, Any]:
    return {
        "host": socket.gethostname(),
        "platform": platform.platform(),
        "python": sys.version.replace("\n", " "),
        "cwd": os.getcwd(),
    }


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, default=json_default) + "\n")


def position_ids(seq_len: int = SEQ_LEN) -> list[int]:
    return list(range(seq_len))


def pad_or_trim(tokens: list[int], seq_len: int = SEQ_LEN, pad_id: int = 0) -> list[int]:
    tokens = [int(t) for t in tokens[:seq_len]]
    return tokens + [pad_id] * max(0, seq_len - len(tokens))


def make_case(case_id: str, description: str, tokens: list[int], semantic: bool, diagnostic: bool, decoded_text: str | None = None) -> dict[str, Any]:
    token_ids = pad_or_trim(tokens)
    mask_positions = [i for i, token in enumerate(token_ids) if token == MASK_TOKEN_ID]
    return {
        "case_id": case_id,
        "human_description": description,
        "token_ids": token_ids,
        "position_ids": position_ids(),
        "attention_mask": [1] * SEQ_LEN,
        "expected_seq_len": SEQ_LEN,
        "expected_last_token_index": SEQ_LEN - 1,
        "mask_positions": mask_positions,
        "is_semantic": semantic,
        "is_diagnostic": diagnostic,
        "decoded_text": decoded_text,
    }


def default_probe_cases() -> list[dict[str, Any]]:
    base_prompt = [151643, 220, 16, 15, 2055, 576, 358, 279, 220, 151643]
    chinese_proxy = [151643, 104859, 3837, 100644, 109944, 151645, 220, 16, 15, 2055]
    openclaw_proxy = [151643, 785, 220, 2413, 7564, 220, 16, 151645, 151643, 279, 2055]
    exactly_128 = [(i * 17 + 11) % 9000 + 1 for i in range(SEQ_LEN)]
    return [
        make_case("zeros", "Diagnostic all-zero token ids; not a semantic prompt.", [0] * SEQ_LEN, False, True),
        make_case("ramp", "Diagnostic increasing token ids.", [1 + (i % 997) for i in range(SEQ_LEN)], False, True),
        make_case("single_token_repeat", "Diagnostic repeated token 220.", [220] * SEQ_LEN, False, True),
        make_case("repeated_frequent_token", "Diagnostic repeated frequent token 220.", [220] * SEQ_LEN, False, True),
        make_case("repeated_rare_token", "Diagnostic repeated high token 151643.", [151643] * SEQ_LEN, False, True),
        make_case("alternating_tokens", "Diagnostic alternating token ids.", [151643 if i % 2 else 220 for i in range(SEQ_LEN)], False, True),
        make_case("alternating_two_tokens", "Diagnostic alternating two tokens.", [16 if i % 2 else 15 for i in range(SEQ_LEN)], False, True),
        make_case("real_prompt_padded", "Token-id semantic proxy for a short English prompt padded to 128.", base_prompt, True, False, "semantic proxy; tokenizer decode unavailable"),
        make_case("short_english_prompt_padded", "Token-id semantic proxy for short English prompt.", base_prompt + [220, 358, 576], True, False, "semantic proxy; tokenizer decode unavailable"),
        make_case("short_chinese_prompt_padded", "Token-id semantic proxy for short Chinese prompt.", chinese_proxy, True, False, "semantic proxy; tokenizer decode unavailable"),
        make_case("openclaw_style_prompt_padded", "Token-id semantic proxy for OpenClaw-style prompt.", openclaw_proxy, True, False, "semantic proxy; tokenizer decode unavailable"),
        make_case("exactly_128_token_synthetic_prompt", "Synthetic non-padding exactly-128 token sequence.", exactly_128, False, True),
        make_case("real_prompt_mask_tail", "Semantic proxy with four mask tokens at tail.", base_prompt + [0] * (SEQ_LEN - len(base_prompt) - 4) + [MASK_TOKEN_ID] * 4, True, False, "semantic proxy with mask tail"),
        make_case("prompt_with_mask_tail", "OpenClaw-style proxy with mask tail.", openclaw_proxy + [0] * (SEQ_LEN - len(openclaw_proxy) - 8) + [MASK_TOKEN_ID] * 8, True, False, "semantic proxy with mask tail"),
    ]


def topk(values: np.ndarray, k: int = 5) -> list[dict[str, float | int]]:
    flat = values.reshape(-1)
    if flat.size == 0:
        return []
    k = min(k, flat.size)
    indices = np.argpartition(flat, -k)[-k:]
    indices = indices[np.argsort(flat[indices])[::-1]]
    return [{"token": int(index), "logit": float(flat[index])} for index in indices]


def tensor_stats(values: np.ndarray) -> dict[str, Any]:
    arr = np.asarray(values)
    finite = arr[np.isfinite(arr)] if np.issubdtype(arr.dtype, np.floating) else arr.reshape(-1)
    return {
        "shape": [int(x) for x in arr.shape],
        "dtype": str(arr.dtype),
        "min": float(np.min(finite)) if finite.size else None,
        "max": float(np.max(finite)) if finite.size else None,
        "mean": float(np.mean(finite)) if finite.size else None,
        "std": float(np.std(finite)) if finite.size else None,
        "nonzero_count": int(np.count_nonzero(arr)),
        "nan_count": int(np.isnan(arr).sum()) if np.issubdtype(arr.dtype, np.floating) else 0,
        "inf_count": int(np.isinf(arr).sum()) if np.issubdtype(arr.dtype, np.floating) else 0,
        "constant": bool(arr.size > 0 and np.all(arr.reshape(-1) == arr.reshape(-1)[0])),
    }


def softmax_stats(values: np.ndarray) -> dict[str, float]:
    arr = values.reshape(-1).astype(np.float64)
    if arr.size == 0:
        return {"top1_probability": 0.0, "entropy": 0.0, "normalized_entropy": 0.0}
    shifted = arr - float(np.max(arr))
    exp = np.exp(shifted)
    denom = float(np.sum(exp))
    probs = exp / denom if denom else np.zeros_like(exp)
    entropy = float(-np.sum(probs * np.log(probs + 1e-300)))
    return {
        "top1_probability": float(np.max(probs)) if probs.size else 0.0,
        "entropy": entropy,
        "normalized_entropy": entropy / math.log(arr.size) if arr.size > 1 else 0.0,
    }


def cosine(a: np.ndarray, b: np.ndarray) -> float | None:
    left = np.asarray(a).reshape(-1).astype(np.float64)
    right = np.asarray(b).reshape(-1).astype(np.float64)
    if left.shape != right.shape:
        return None
    denom = float(np.linalg.norm(left) * np.linalg.norm(right))
    return float(np.dot(left, right) / denom) if denom else 0.0


def kl_divergence(a: np.ndarray, b: np.ndarray) -> float | None:
    left = np.asarray(a).reshape(-1).astype(np.float64)
    right = np.asarray(b).reshape(-1).astype(np.float64)
    if left.shape != right.shape:
        return None
    left = left - float(np.max(left))
    right = right - float(np.max(right))
    p = np.exp(left)
    q = np.exp(right)
    p = p / float(np.sum(p))
    q = q / float(np.sum(q))
    return float(np.sum(p * (np.log(p + 1e-300) - np.log(q + 1e-300))))


def compare_vectors(reference: np.ndarray, candidate: np.ndarray) -> dict[str, Any]:
    ref = np.asarray(reference).reshape(-1).astype(np.float32)
    cand = np.asarray(candidate).reshape(-1).astype(np.float32)
    if ref.shape != cand.shape:
        return {"shape_match": False, "reference_shape": list(ref.shape), "candidate_shape": list(cand.shape)}
    diff = cand.astype(np.float64) - ref.astype(np.float64)
    ref_norm = float(np.linalg.norm(ref.astype(np.float64)))
    ref_top = topk(ref, 5)
    cand_top = topk(cand, 5)
    ref_top1 = int(ref_top[0]["token"]) if ref_top else None
    cand_top1 = int(cand_top[0]["token"]) if cand_top else None
    cand_top5 = {int(item["token"]) for item in cand_top}
    cand_softmax = softmax_stats(cand)
    return {
        "shape_match": True,
        "top1_agreement": ref_top1 == cand_top1,
        "ref_top1": ref_top1,
        "candidate_top1": cand_top1,
        "top5_overlap_count": len({int(item["token"]) for item in ref_top} & cand_top5),
        "ref_top1_in_candidate_top5": ref_top1 in cand_top5 if ref_top1 is not None else False,
        "cosine": cosine(ref, cand),
        "l2_relative_error": float(np.linalg.norm(diff) / ref_norm) if ref_norm else None,
        "max_abs_error": float(np.max(np.abs(diff))) if diff.size else None,
        "mean_abs_error": float(np.mean(np.abs(diff))) if diff.size else None,
        "kl_divergence": kl_divergence(ref, cand),
        "candidate_entropy": cand_softmax["entropy"],
        "candidate_normalized_entropy": cand_softmax["normalized_entropy"],
        "candidate_top1_probability": cand_softmax["top1_probability"],
        "candidate_nonzero_count": int(np.count_nonzero(cand)),
        "candidate_nan_count": int(np.isnan(cand).sum()),
        "candidate_inf_count": int(np.isinf(cand).sum()),
        "reference_top5": ref_top,
        "candidate_top5": cand_top,
    }


def read_logits_bin(path: Path) -> np.ndarray:
    with path.open("rb") as handle:
        header = np.fromfile(handle, dtype=np.int32, count=2)
        if header.size != 2:
            raise RuntimeError(f"invalid logits header in {path}")
        n_tokens, n_vocab = int(header[0]), int(header[1])
        data = np.fromfile(handle, dtype=np.float32)
    expected = n_tokens * n_vocab
    if data.size != expected:
        raise RuntimeError(f"invalid logits size in {path}: expected={expected} actual={data.size}")
    return data.reshape(n_tokens, n_vocab)


def read_manifest_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))

