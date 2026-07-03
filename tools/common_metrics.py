#!/usr/bin/env python3
"""Common tensor/logits metrics for Dream7B S100P v5 research."""
from __future__ import annotations
import hashlib, json, math
from pathlib import Path
from typing import Any, Dict
import numpy as np


def sha256_file(path: str | Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(chunk_size), b''):
            h.update(chunk)
    return h.hexdigest()


def tensor_stats(x: np.ndarray) -> Dict[str, Any]:
    arr = np.asarray(x)
    finite = arr[np.isfinite(arr)] if np.issubdtype(arr.dtype, np.floating) else arr
    return {
        'shape': list(arr.shape),
        'dtype': str(arr.dtype),
        'min': float(np.min(finite)) if finite.size else None,
        'max': float(np.max(finite)) if finite.size else None,
        'mean': float(np.mean(finite)) if finite.size else None,
        'std': float(np.std(finite)) if finite.size else None,
        'absmax': float(np.max(np.abs(finite))) if finite.size else None,
        'nonzero_count': int(np.count_nonzero(arr)),
        'nan_count': int(np.isnan(arr).sum()) if np.issubdtype(arr.dtype, np.floating) else 0,
        'inf_count': int(np.isinf(arr).sum()) if np.issubdtype(arr.dtype, np.floating) else 0,
        'constant': bool(arr.size > 0 and np.all(arr == arr.flat[0])),
    }


def stable_softmax(logits: np.ndarray) -> np.ndarray:
    v = np.asarray(logits, dtype=np.float64).reshape(-1)
    v = v - np.max(v)
    e = np.exp(v)
    s = np.sum(e)
    if not np.isfinite(s) or s == 0:
        return np.full_like(v, 1.0 / v.size)
    return e / s


def logits_compare(ref: np.ndarray, cand: np.ndarray, topk: int = 5) -> Dict[str, Any]:
    r = np.asarray(ref, dtype=np.float64).reshape(-1)
    c = np.asarray(cand, dtype=np.float64).reshape(-1)
    if r.shape != c.shape:
        return {'shape_match': False, 'ref_shape': list(r.shape), 'cand_shape': list(c.shape)}
    rt = np.argsort(r)[-topk:][::-1]
    ct = np.argsort(c)[-topk:][::-1]
    dot = float(np.dot(r, c))
    denom = float(np.linalg.norm(r) * np.linalg.norm(c))
    cosine = dot / denom if denom else 0.0
    rp = stable_softmax(r); cp = stable_softmax(c)
    entropy = -float(np.sum(cp * np.log(cp + 1e-300)))
    norm_entropy = entropy / math.log(c.size) if c.size > 1 else 0.0
    kl = float(np.sum(rp * (np.log(rp + 1e-300) - np.log(cp + 1e-300))))
    return {
        'shape_match': True,
        'ref_top1': int(rt[0]),
        'cand_top1': int(ct[0]),
        'top1_agreement': bool(rt[0] == ct[0]),
        'ref_top1_in_candidate_top5': bool(rt[0] in ct),
        'top5_overlap_count': int(len(set(map(int, rt)) & set(map(int, ct)))),
        'cosine': cosine,
        'l2_relative_error': float(np.linalg.norm(r - c) / (np.linalg.norm(r) + 1e-12)),
        'max_abs_error': float(np.max(np.abs(r - c))),
        'mean_abs_error': float(np.mean(np.abs(r - c))),
        'kl_divergence': kl,
        'candidate_entropy': entropy,
        'candidate_normalized_entropy': norm_entropy,
        'candidate_top1_probability': float(cp[ct[0]]),
        'candidate_nonzero_count': int(np.count_nonzero(c)),
    }


def write_json(path: str | Path, data: Any) -> None:
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
