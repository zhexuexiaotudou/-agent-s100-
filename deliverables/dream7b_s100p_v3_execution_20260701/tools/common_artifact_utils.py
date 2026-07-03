#!/usr/bin/env python3
"""Common utilities for Dream7B/S100P evidence scripts.

These helpers are runtime-agnostic. Codex should import them from repo tools or
copy the useful functions into existing scripts.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import numpy as np


def utc_now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def sha256_file(path: str | Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while True:
            b = f.read(chunk_size)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def ensure_parent(path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def write_json(path: str | Path, obj: Any) -> None:
    ensure_parent(path)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, indent=2, ensure_ascii=False, sort_keys=True)
        f.write('\n')


def read_json(path: str | Path) -> Any:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_array(path: str | Path) -> np.ndarray:
    path = Path(path)
    if path.suffix == '.npy':
        return np.load(path)
    raise ValueError(f'Unsupported array extension: {path}')


def percentile_stats(a: np.ndarray) -> Dict[str, float]:
    flat = np.asarray(a).astype(np.float64).ravel()
    if flat.size == 0:
        return {k: math.nan for k in ['p0','p1','p5','p50','p95','p99','p100']}
    qs = np.percentile(flat, [0, 1, 5, 50, 95, 99, 100])
    return {k: float(v) for k, v in zip(['p0','p1','p5','p50','p95','p99','p100'], qs)}


def array_stats(a: np.ndarray) -> Dict[str, Any]:
    arr = np.asarray(a)
    flat = arr.astype(np.float64).ravel() if arr.size else np.asarray([], dtype=np.float64)
    finite = np.isfinite(flat)
    finite_vals = flat[finite]
    stats: Dict[str, Any] = {
        'shape': list(arr.shape),
        'dtype': str(arr.dtype),
        'size': int(arr.size),
        'nan_count': int(np.isnan(flat).sum()) if flat.size else 0,
        'inf_count': int(np.isinf(flat).sum()) if flat.size else 0,
        'nonzero_count': int(np.count_nonzero(arr)),
        'allzero': bool(arr.size > 0 and np.count_nonzero(arr) == 0),
        'constant': bool(arr.size > 0 and finite_vals.size > 0 and np.nanmin(finite_vals) == np.nanmax(finite_vals)),
    }
    if finite_vals.size:
        stats.update({
            'min': float(np.min(finite_vals)),
            'max': float(np.max(finite_vals)),
            'mean': float(np.mean(finite_vals)),
            'std': float(np.std(finite_vals)),
            'abs_max': float(np.max(np.abs(finite_vals))),
        })
        stats.update(percentile_stats(finite_vals))
    else:
        stats.update({k: math.nan for k in ['min','max','mean','std','abs_max','p0','p1','p5','p50','p95','p99','p100']})
    return stats


def topk(logits: np.ndarray, k: int = 20) -> List[Dict[str, float | int]]:
    x = np.asarray(logits).reshape(-1).astype(np.float64)
    if x.size == 0:
        return []
    k = min(k, x.size)
    idx = np.argpartition(-x, np.arange(k))[:k]
    idx = idx[np.argsort(-x[idx])]
    return [{'index': int(i), 'value': float(x[i])} for i in idx]


def stable_softmax(x: np.ndarray) -> np.ndarray:
    v = np.asarray(x).reshape(-1).astype(np.float64)
    if v.size == 0:
        return v
    m = np.nanmax(v)
    ex = np.exp(v - m)
    s = np.sum(ex)
    if not np.isfinite(s) or s == 0:
        return np.full_like(v, np.nan, dtype=np.float64)
    return ex / s


def entropy_metrics(logits: np.ndarray) -> Dict[str, float]:
    p = stable_softmax(logits)
    if p.size == 0 or np.isnan(p).all():
        return {'entropy': math.nan, 'normalized_entropy': math.nan, 'top1_probability': math.nan}
    p_safe = np.clip(p, 1e-300, 1.0)
    ent = float(-np.sum(p_safe * np.log(p_safe)))
    norm = float(ent / math.log(p.size)) if p.size > 1 else 0.0
    top1p = float(np.max(p))
    return {'entropy': ent, 'normalized_entropy': norm, 'top1_probability': top1p}


def logits_report(logits: np.ndarray, k: int = 20) -> Dict[str, Any]:
    out = array_stats(logits)
    out.update(entropy_metrics(logits))
    out['topk'] = topk(logits, k=k)
    return out


def markdown_table(rows: list[dict[str, Any]], columns: list[str]) -> str:
    lines = ['| ' + ' | '.join(columns) + ' |', '| ' + ' | '.join(['---'] * len(columns)) + ' |']
    for r in rows:
        lines.append('| ' + ' | '.join(str(r.get(c, '')) for c in columns) + ' |')
    return '\n'.join(lines) + '\n'
