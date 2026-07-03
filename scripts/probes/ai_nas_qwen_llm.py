#!/usr/bin/env python3
"""Qwen LLM text intelligence for AI-NAS.

Wraps the local Qwen2.5-1.5B OpenAI-compatible gateway (port 18080).
Provides: summarize, rag_answer, classify, extract_metadata, rewrite_query,
suggest_archive, extract_movie_metadata, generate_report.

All responses carry evidence blocks with model, confidence, source.
No external API dependencies — uses only the local model.
"""

from __future__ import annotations

import json, logging, os, time, urllib.error, urllib.request
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_QWEN_URL = "http://127.0.0.1:18080/v1"
DEFAULT_QWEN_MODEL = "Qwen2.5-1.5B-Instruct-S100P-official"


def _get_config():
    return {
        "base_url": os.environ.get("AI_NAS_QWEN_BASE_URL", DEFAULT_QWEN_URL),
        "model": os.environ.get("AI_NAS_QWEN_MODEL", DEFAULT_QWEN_MODEL),
        "timeout": int(os.environ.get("AI_NAS_QWEN_TIMEOUT", "120")),
        "max_tokens": int(os.environ.get("AI_NAS_QWEN_MAX_TOKENS", "2048")),
    }


_LAST_TS = 0.0

def _rate_limit():
    global _LAST_TS
    delay = 0.2
    now = time.monotonic()
    wait = _LAST_TS + delay - now
    if wait > 0: time.sleep(wait)
    _LAST_TS = time.monotonic()


def _invoke(messages: list[dict], *, max_tokens: int = 1024, temperature: float = 0.3, caller: str = "unknown") -> dict:
    cfg = _get_config()
    url = f"{cfg['base_url'].rstrip('/')}/chat/completions"
    payload = {"model": cfg["model"], "messages": messages, "max_tokens": max_tokens, "temperature": temperature, "stream": False}
    headers = {"Content-Type": "application/json"}
    _rate_limit()
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=cfg["timeout"]) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        choice = (result.get("choices") or [{}])[0]
        msg = choice.get("message", {})
        answer = msg.get("content", "") or ""
        finish = choice.get("finish_reason", "")
        usage = result.get("usage", {})
        confidence = 0.9 if finish == "stop" else 0.5 if finish == "length" else 0.0
        return {"ok": True, "answer": answer, "model": cfg["model"], "finish_reason": finish, "usage": usage, "evidence": {"caller": caller, "model": cfg["model"], "source": "qwen_llm_local", "confidence": confidence, "finish_reason": finish}}
    except Exception as e:
        return {"ok": False, "answer": "", "error": str(e)[:200], "evidence": {"caller": caller, "model": cfg["model"], "source": "qwen_llm_local", "confidence": 0.0, "error": str(e)[:200]}}


def health() -> dict:
    cfg = _get_config()
    return {"provider": "qwen_llm_local", "model": cfg["model"], "base_url": cfg["base_url"], "capabilities": ["summarize", "rag_answer", "classify", "extract_metadata", "rewrite_query", "suggest_archive", "extract_movie_metadata", "generate_report"]}


def summarize(text: str, max_chars: int = 500) -> dict:
    text = text[:16000]
    msgs = [{"role": "system", "content": "你是一个NAS系统的文档摘要助手。用2-5句中文总结以下文档内容，聚焦主题、关键实体和文档类型。不要编造信息。"}, {"role": "user", "content": text}]
    result = _invoke(msgs, max_tokens=min(max_chars, 1024), caller="summarize")
    result["summary"] = result.get("answer", "")
    result["evidence"]["input_chars"] = len(text)
    return result


def rag_answer(query: str, chunks: list[dict]) -> dict:
    ctx_lines = []
    cit_map = {}
    for i, c in enumerate(chunks, 1):
        cit_map[i] = c.get("source", f"chunk_{i}")
        ctx_lines.append(f"[{i}] {c.get('source','?')} (score={c.get('score','N/A')})\n{c.get('text','')}")
    ctx = "\n\n---\n\n".join(ctx_lines)
    msgs = [{"role": "system", "content": f"你是NAS系统的AI助手。仅根据以下上下文回答问题。引用时用方括号标注编号。如果上下文不足以回答，明确说明。\n\n上下文:\n{ctx}"}, {"role": "user", "content": query}]
    result = _invoke(msgs, max_tokens=2048, caller="rag_answer")
    import re
    cited = set()
    for m in re.finditer(r'\[(\d+)\]', result.get("answer", "")):
        idx = int(m.group(1))
        if idx in cit_map: cited.add(idx)
    result["citations"] = [{"index": i, "source": cit_map[i]} for i in sorted(cited)]
    result["evidence"]["chunks"] = len(chunks)
    result["evidence"]["cited"] = len(cited)
    return result


def classify(text: str, categories: list[str]) -> dict:
    cats = "\n".join(f"- {c}" for c in categories)
    msgs = [{"role": "system", "content": f"你是文件分类助手。将以下文本分入以下类别之一，只回复类别名称。\n\n类别:\n{cats}"}, {"role": "user", "content": text[:2000]}]
    result = _invoke(msgs, max_tokens=64, temperature=0.1, caller="classify")
    raw = result.get("answer", "").strip()
    matched = next((c for c in categories if c.lower() in raw.lower()), raw)
    result["category"] = matched
    return result


def extract_metadata(text: str, fields: list[str]) -> dict:
    fd = "\n".join(f"- {f}" for f in fields)
    msgs = [{"role": "system", "content": f"你是结构化数据提取助手。从文本中提取以下字段，回复JSON对象。无法确定的字段设为null。\n\n字段:\n{fd}"}, {"role": "user", "content": text[:4000]}]
    result = _invoke(msgs, max_tokens=1024, temperature=0.1, caller="extract_metadata")
    answer = result.get("answer", "").strip()
    extracted = {}
    try:
        extracted = json.loads(answer)
    except json.JSONDecodeError:
        import re
        m = re.search(r'\{[^}]+\}', answer, re.DOTALL)
        if m:
            try: extracted = json.loads(m.group())
            except json.JSONDecodeError: pass
    for f in fields:
        if f not in extracted: extracted[f] = None
    result["extracted"] = extracted
    result["evidence"]["fields"] = fields
    result["evidence"]["found"] = sum(1 for v in extracted.values() if v is not None)
    return result


def rewrite_query(query: str) -> dict:
    msgs = [{"role": "system", "content": "你是搜索意图分析助手。分析用户查询，输出JSON:\n- query_type: file_search|photo_search|document_search|movie_search|music_search|general\n- keywords: 关键词列表\n- file_types: 文件扩展名列表\n- folder: 文件夹名或null\n输出只包含JSON。"}, {"role": "user", "content": query}]
    result = _invoke(msgs, max_tokens=256, temperature=0.1, caller="rewrite_query")
    answer = result.get("answer", "").strip()
    intent = {"query_type": "general", "keywords": [], "file_types": [], "folder": None}
    try: intent.update(json.loads(answer))
    except json.JSONDecodeError:
        import re; m = re.search(r'\{[^}]+\}', answer, re.DOTALL)
        if m:
            try: intent.update(json.loads(m.group()))
            except json.JSONDecodeError: pass
    result["intent"] = intent
    return result


def suggest_archive(file_info: dict) -> dict:
    fname = file_info.get("name", "unknown")
    fpath = file_info.get("path", "unknown")
    fcat = file_info.get("category", "unknown")
    snippet = file_info.get("snippet", "")[:1000]
    msgs = [{"role": "system", "content": "你是文件归档助手。根据文件名、路径、类别和内容片段，建议归档目录和可选重命名。回复JSON: {\"target_folder\": \"建议路径\", \"rename\": null或新文件名, \"reason\": \"一句话中文原因\"}。只输出JSON。"}, {"role": "user", "content": f"文件: {fname}\n当前路径: {fpath}\n类别: {fcat}\n内容片段:\n{snippet or '(无)'}"}]
    result = _invoke(msgs, max_tokens=512, temperature=0.2, caller="suggest_archive")
    answer = result.get("answer", "").strip()
    suggestion = {"target_folder": fpath, "rename": None, "reason": ""}
    try: suggestion.update(json.loads(answer))
    except json.JSONDecodeError:
        import re; m = re.search(r'\{[^}]+\}', answer, re.DOTALL)
        if m:
            try: suggestion.update(json.loads(m.group()))
            except json.JSONDecodeError: pass
    result["suggestion"] = suggestion
    return result


def extract_movie_metadata(filename: str) -> dict:
    msgs = [{"role": "system", "content": "你是媒体文件分析助手。从文件名提取影视元数据。回复JSON: {\"media_type\":\"movie\"或\"tv_show\"或\"unknown\",\"title\":null或标题,\"year\":null或年份,\"season\":null或季号,\"episode\":null或集号,\"quality\":null或画质}。只输出JSON。"}, {"role": "user", "content": filename}]
    result = _invoke(msgs, max_tokens=256, temperature=0.1, caller="extract_movie_metadata")
    answer = result.get("answer", "").strip()
    meta = {"media_type": "unknown", "title": None, "year": None, "season": None, "episode": None, "quality": None}
    try: meta.update(json.loads(answer))
    except json.JSONDecodeError:
        import re; m = re.search(r'\{[^}]+\}', answer, re.DOTALL)
        if m:
            try: meta.update(json.loads(m.group()))
            except json.JSONDecodeError: pass
    result["metadata"] = meta
    return result


def generate_report(title: str, sections: list[dict]) -> dict:
    sec_text = ""
    for s in sections:
        sec_text += f"\n## {s.get('heading','')}\n{s.get('data_summary','(无数据)')}\n"
    msgs = [{"role": "system", "content": "你是NAS系统报告生成助手。根据提供的数据摘要生成中文Markdown格式报告。顶部放执行摘要。不要编造统计数据，缺失数据的部分明确标注。"}, {"role": "user", "content": f"报告标题: {title}\n\n数据部分:{sec_text}\n\n生成完整报告。"}]
    result = _invoke(msgs, max_tokens=4096, caller="generate_report")
    result["evidence"]["title"] = title
    result["evidence"]["sections"] = len(sections)
    return result


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    print(json.dumps(health(), ensure_ascii=False, indent=2))
