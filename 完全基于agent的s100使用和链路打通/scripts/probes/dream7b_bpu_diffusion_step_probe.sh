#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
prompt="${2:-Explain why S100P BPU matters for Dream 7B in OpenClaw.}"

tokenizer_venv="${DREAM7B_TOKENIZER_VENV:-/mnt/nas/openclaw/runtimes/dream7b-tokenizer-venv}"
tokenizer_dir="${DREAM7B_TOKENIZER:-/mnt/nas/openclaw/models/dream7b/tokenizer}"
seq_len="${DREAM7B_BPU_SEQ_LEN:-16}"
min_mask_count="${DREAM7B_BPU_MIN_MASK_COUNT:-4}"
top_k="${DREAM7B_BPU_TOP_K:-5}"

case "$report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_root" >&2
    exit 2
    ;;
esac

if [[ ! -x "$tokenizer_venv/bin/python" ]]; then
  echo "Missing Dream 7B tokenizer venv: $tokenizer_venv" >&2
  exit 4
fi

if [[ ! -d "$tokenizer_dir" ]]; then
  echo "Missing Dream 7B tokenizer directory: $tokenizer_dir" >&2
  exit 4
fi

if ! command -v dream7b-bpu-forward >/dev/null 2>&1; then
  echo "Missing deployed S100P command: dream7b-bpu-forward" >&2
  exit 4
fi

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_diffusion_step_$stamp"
forward_dir="$run_dir/forward"
mkdir -p "$run_dir"

tokens_bin="$run_dir/tokens.bin"
input_json="$run_dir/input.json"
summary_json="$run_dir/summary.json"
summary_md="$run_dir/summary.md"

"$tokenizer_venv/bin/python" - "$tokenizer_dir" "$prompt" "$seq_len" "$min_mask_count" "$tokens_bin" "$input_json" <<'PY'
import json
import sys
from pathlib import Path

import numpy as np
from transformers import AutoTokenizer

tokenizer_dir, prompt, seq_len_text, min_mask_count_text, tokens_bin, input_json = sys.argv[1:7]
seq_len = int(seq_len_text)
min_mask_count = int(min_mask_count_text)
if min_mask_count <= 0 or min_mask_count >= seq_len:
    raise SystemExit(f"min_mask_count must be between 1 and seq_len-1, got {min_mask_count}")

tok = AutoTokenizer.from_pretrained(tokenizer_dir, trust_remote_code=True, local_files_only=True)
if prompt.startswith("<|im_start|>"):
    prepared = prompt
else:
    prepared = f"<|im_start|>user\n{prompt}<|im_end|>\n<|im_start|>assistant\n"

prompt_ids = tok.encode(prepared)
mask_id = int(tok.mask_token_id)
prefix_limit = seq_len - min_mask_count
if len(prompt_ids) >= seq_len:
    prefix_ids = prompt_ids[-prefix_limit:]
    fit_mode = "truncate_prompt_keep_min_masks"
else:
    prefix_ids = prompt_ids
    fit_mode = "natural_prompt_then_masks"

mask_count = seq_len - len(prefix_ids)
tokens = prefix_ids + [mask_id] * mask_count
if len(tokens) != seq_len:
    raise SystemExit(f"internal error: built {len(tokens)} tokens, expected {seq_len}")

np.asarray(tokens, dtype=np.int32).tofile(tokens_bin)
payload = {
    "prompt": prompt,
    "prepared_prompt": prepared,
    "seq_len": seq_len,
    "min_mask_count": min_mask_count,
    "fit_mode": fit_mode,
    "prompt_token_count": len(prompt_ids),
    "prefix_token_count": len(prefix_ids),
    "mask_token_id": mask_id,
    "mask_positions": [i for i, value in enumerate(tokens) if value == mask_id],
    "input_tokens": tokens,
    "input_text": tok.decode(tokens, skip_special_tokens=False),
}
Path(input_json).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY

dream7b-bpu-forward \
  --tokens-bin "$tokens_bin" \
  --output-dir "$forward_dir" \
  --save-logits \
  --top-k "$top_k" > "$run_dir/forward.stdout" 2> "$run_dir/forward.stderr"

"$tokenizer_venv/bin/python" - "$tokenizer_dir" "$input_json" "$forward_dir/logits.npy" "$forward_dir/summary.json" "$summary_json" "$summary_md" "$top_k" <<'PY'
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
from transformers import AutoTokenizer

tokenizer_dir, input_json, logits_npy, forward_summary_json, summary_json, summary_md, top_k_text = sys.argv[1:8]
top_k = int(top_k_text)
tok = AutoTokenizer.from_pretrained(tokenizer_dir, trust_remote_code=True, local_files_only=True)
input_payload = json.loads(Path(input_json).read_text(encoding="utf-8"))
forward_summary = json.loads(Path(forward_summary_json).read_text(encoding="utf-8"))
logits = np.load(logits_npy)
if logits.ndim != 3 or logits.shape[0] != 1:
    raise SystemExit(f"unexpected logits shape: {logits.shape}")

# DreamGenerationMixin._sample uses logits[:, :1] plus logits[:, :-1] before
# selecting mask positions. Keep the same shift here.
shifted = np.concatenate([logits[:, :1, :], logits[:, :-1, :]], axis=1)
tokens = list(input_payload["input_tokens"])
mask_positions = list(input_payload["mask_positions"])
updates = []
for pos in mask_positions:
    scores = shifted[0, pos].astype(np.float32, copy=False)
    token_id = int(np.argmax(scores))
    tokens[pos] = token_id
    k = min(top_k, scores.shape[0])
    top_indices = np.argpartition(scores, -k)[-k:]
    top_indices = top_indices[np.argsort(scores[top_indices])[::-1]]
    updates.append({
        "position": int(pos),
        "selected_token_id": token_id,
        "selected_score": float(scores[token_id]),
        "topk": [{"token_id": int(idx), "score": float(scores[idx])} for idx in top_indices],
    })

decoded_once = tok.decode(tokens, skip_special_tokens=True)
payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_bpu_diffusion_step_probe",
    "input": input_payload,
    "forward_summary": str(Path(forward_summary_json)),
    "logits_npy": str(Path(logits_npy)),
    "logits_shape": list(logits.shape),
    "logits_shift": "dream_generation_cat_logits_first_then_previous_positions",
    "updated_tokens": tokens,
    "decoded_once": decoded_once,
    "mask_updates": updates,
    "notes": [
        "This is one host-side Dream diffusion step over S100P BPU logits, not a complete text generation service.",
        "The probe keeps DreamGenerationMixin._sample logits shift semantics before selecting masked positions.",
    ],
}
Path(summary_json).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

lines = [
    "# Dream 7B BPU Diffusion Step Probe",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- forward_summary: {payload['forward_summary']}",
    f"- logits_npy: {payload['logits_npy']}",
    f"- logits_shape: {payload['logits_shape']}",
    f"- prompt_token_count: {input_payload['prompt_token_count']}",
    f"- prefix_token_count: {input_payload['prefix_token_count']}",
    f"- mask_positions: {input_payload['mask_positions']}",
    "",
    "## Selected Mask Tokens",
    "",
    "| Position | Token ID | Score |",
    "| ---: | ---: | ---: |",
]
for item in updates:
    lines.append(f"| {item['position']} | {item['selected_token_id']} | {item['selected_score']:.6f} |")
lines.extend([
    "",
    "## Decoded One-Step Output",
    "",
    "```text",
    decoded_once,
    "```",
    "",
    "## Boundary",
    "",
    "- This is one Dream diffusion sampling step using S100P BPU logits.",
    "- It does not claim full multi-step Dream text generation yet.",
])
Path(summary_md).write_text("\n".join(lines) + "\n", encoding="utf-8")
print(summary_md)
PY
