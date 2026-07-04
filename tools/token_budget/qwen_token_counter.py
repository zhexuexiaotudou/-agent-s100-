from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .tokenizer_identity import TokenizerBundle, build_tokenizer_bundle


def compact_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class QwenTokenCounter:
    """Counts tokens with the local Qwen tokenizer when available."""

    def __init__(self, tokenizer_path: Optional[str] = None) -> None:
        bundle: TokenizerBundle = build_tokenizer_bundle(tokenizer_path)
        self.tokenizer = bundle.tokenizer
        self.identity = bundle.identity
        self.backend = self.identity["backend"]

    @property
    def real_tokenizer_available(self) -> bool:
        return bool(self.identity.get("real_tokenizer_available"))

    def count_text_tokens(self, text: Any) -> int:
        if text is None:
            return 0
        value = str(text)
        if not value:
            return 0
        if self.backend == "transformers_auto" and self.tokenizer is not None:
            return len(self.tokenizer.encode(value, add_special_tokens=False))
        if self.backend == "tokenizers_json" and self.tokenizer is not None:
            return len(self.tokenizer.encode(value).ids)
        return max(1, math.ceil(len(value) / 3.5))

    def count_messages_tokens(self, messages: List[Dict[str, Any]]) -> int:
        if self.backend == "transformers_auto" and self.tokenizer is not None:
            apply_chat_template = getattr(self.tokenizer, "apply_chat_template", None)
            if callable(apply_chat_template):
                rendered = apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
                return self.count_text_tokens(rendered)
        return self.count_text_tokens(compact_json(messages))

    def count_payload_tokens(self, payload_json: Any) -> int:
        if isinstance(payload_json, str):
            return self.count_text_tokens(payload_json)
        return self.count_text_tokens(compact_json(payload_json))

    def batch_count_cases(self, cases_jsonl: str | Path) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        path = Path(cases_jsonl)
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                case = json.loads(line)
                row = {
                    "case_id": case.get("case_id"),
                    "task_type": case.get("task_type"),
                    "prompt_tokens": self.count_text_tokens(case.get("user_prompt", "")),
                    "context_tokens": self.count_text_tokens(case.get("context_text", "")),
                    "payload_tokens": self.count_payload_tokens(case),
                }
                out.append(row)
        return out

    def count_jsonl_cases(self, cases_jsonl: str | Path) -> List[Dict[str, Any]]:
        return self.batch_count_cases(cases_jsonl)


def count_text_tokens(text: Any, tokenizer_path: Optional[str] = None) -> int:
    return QwenTokenCounter(tokenizer_path).count_text_tokens(text)


def count_messages_tokens(messages: List[Dict[str, Any]], tokenizer_path: Optional[str] = None) -> int:
    return QwenTokenCounter(tokenizer_path).count_messages_tokens(messages)


def count_payload_tokens(payload_json: Any, tokenizer_path: Optional[str] = None) -> int:
    return QwenTokenCounter(tokenizer_path).count_payload_tokens(payload_json)


def batch_count_cases(cases_jsonl: str | Path, tokenizer_path: Optional[str] = None) -> List[Dict[str, Any]]:
    return QwenTokenCounter(tokenizer_path).batch_count_cases(cases_jsonl)


def count_jsonl_cases(cases_jsonl: str | Path, tokenizer_path: Optional[str] = None) -> List[Dict[str, Any]]:
    return QwenTokenCounter(tokenizer_path).count_jsonl_cases(cases_jsonl)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Count text or JSONL cases with the local Qwen tokenizer.")
    parser.add_argument("--text")
    parser.add_argument("--cases-jsonl")
    parser.add_argument("--tokenizer-path")
    args = parser.parse_args()

    counter = QwenTokenCounter(args.tokenizer_path)
    if args.text is not None:
        print(json.dumps({"tokens": counter.count_text_tokens(args.text), "identity": counter.identity}, ensure_ascii=False, indent=2))
        return
    if args.cases_jsonl:
        print(json.dumps(counter.batch_count_cases(args.cases_jsonl), ensure_ascii=False, indent=2))
        return
    print(json.dumps(counter.identity, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
