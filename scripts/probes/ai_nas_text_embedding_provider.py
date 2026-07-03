#!/usr/bin/env python3
"""Local-only text embedding provider for AI-NAS.

Uses numpy TF-IDF with Chinese bigram + English word tokenization.
No external API dependencies.
"""

from __future__ import annotations
import hashlib, json, logging, math, os, re
from collections import defaultdict
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

def _default_dim() -> int:
    try: return int(os.environ.get("AI_NAS_EMBEDDING_DIM", "384"))
    except ValueError: return 384

def embedding_provider_status() -> dict:
    return {"provider": "ai_nas_text_embedding_provider", "backend": "local_tfidf", "dim": _default_dim(), "capabilities": ["embed_text", "embed_batch", "cosine_similarity", "semantic_search"]}

_CHINESE_PAT = re.compile(r'[\u4e00-\u9fff]+')
_EN_PAT = re.compile(r'[a-zA-Z0-9]+')

def _tokenize(text: str) -> list[str]:
    tokens = []
    chinese_chars = []
    for ch in text:
        if '\u4e00' <= ch <= '\u9fff':
            chinese_chars.append(ch)
        else:
            if len(chinese_chars) >= 2:
                for i in range(len(chinese_chars) - 1):
                    tokens.append(''.join(chinese_chars[i:i+2]))
            chinese_chars = []
    if len(chinese_chars) >= 2:
        for i in range(len(chinese_chars) - 1):
            tokens.append(''.join(chinese_chars[i:i+2]))
    for m in _EN_PAT.finditer(text.lower()):
        tokens.append(m.group())
    return tokens

_VOCAB: dict[str, int] = {}
_IDF: dict[str, float] = {}
_DOC_COUNT = 0

def _build_vocab(corpus: list[str]):
    global _VOCAB, _IDF, _DOC_COUNT
    df = defaultdict(int)
    all_tokens = set()
    for text in corpus:
        tokens = set(_tokenize(text))
        for t in tokens:
            df[t] += 1
            all_tokens.add(t)
    _VOCAB = {t: i for i, t in enumerate(sorted(all_tokens))}
    _DOC_COUNT = len(corpus)
    for t, idx in _VOCAB.items():
        _IDF[t] = math.log((_DOC_COUNT + 1) / (df.get(t, 1) + 1)) + 1.0

def _tfidf_vector(text: str, dim: int | None = None) -> list[float]:
    if not _VOCAB:
        _build_vocab([text])
    tokens = _tokenize(text)
    if not tokens:
        return [0.0] * (dim or len(_VOCAB))
    tf = defaultdict(float)
    for t in tokens:
        if t in _VOCAB:
            tf[t] += 1.0
    norm = math.sqrt(sum(v * v for v in tf.values()))
    if norm > 0:
        for t in tf:
            tf[t] /= norm
    vec = np.zeros(len(_VOCAB))
    for t, v in tf.items():
        idx = _VOCAB.get(t)
        if idx is not None:
            vec[idx] = v * _IDF.get(t, 1.0)
    if dim and dim < len(_VOCAB):
        reduced = np.zeros(dim)
        for i in range(len(_VOCAB)):
            h = int(hashlib.md5(str(i).encode()).hexdigest(), 16) % dim
            reduced[h] += vec[i]
        vec = reduced
    n = np.linalg.norm(vec)
    if n > 0:
        vec = vec / n
    return vec.tolist()

def embed_text(text: str, *, dim: int | None = None) -> dict:
    dim = dim or _default_dim()
    vec = _tfidf_vector(text, dim)
    return {"ok": True, "vector": vec, "dim": len(vec), "backend": "local_tfidf", "model": "local_tfidf_v1", "evidence": {"source": "embedding_local", "model": "local_tfidf_v1", "backend": "local", "vocab_size": len(_VOCAB)}}

def embed_batch(texts: list[str], *, dim: int | None = None) -> dict:
    dim = dim or _default_dim()
    _build_vocab(texts)
    vectors = [_tfidf_vector(t, dim) for t in texts]
    return {"ok": True, "vectors": vectors, "dim": len(vectors[0]) if vectors else 0, "backend": "local_tfidf", "evidence": {"source": "embedding_local", "count": len(vectors), "vocab_size": len(_VOCAB)}}

def cosine_similarity(a: list[float], b: list[float]) -> float:
    va, vb = np.array(a), np.array(b)
    na, nb = np.linalg.norm(va), np.linalg.norm(vb)
    if na == 0 or nb == 0: return 0.0
    return float(np.dot(va, vb) / (na * nb))

def semantic_search(query: str, documents: list[str], *, top_k: int = 5, dim: int | None = None) -> dict:
    qr = embed_text(query, dim=dim)
    if not qr["ok"]:
        return {"ok": False, "error": "embedding_failed", "results": []}
    dr = embed_batch(documents, dim=len(qr["vector"]))
    if not dr["ok"]:
        return {"ok": False, "error": "batch_embedding_failed", "results": []}
    scores = []
    for i, dv in enumerate(dr["vectors"]):
        s = cosine_similarity(qr["vector"], dv)
        scores.append((i, documents[i], s))
    scores.sort(key=lambda x: x[2], reverse=True)
    results = [{"index": idx, "text": txt[:200], "score": round(sc, 4)} for idx, txt, sc in scores[:top_k] if sc > 0.01]
    return {"ok": True, "results": results, "evidence": {"source": "semantic_search", "backend": qr["backend"], "query_dim": len(qr["vector"]), "total_docs": len(documents), "returned": len(results)}}
