#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/mnt/nas/openclaw/reports/models}"
prompt="${2:-Explain why S100P BPU matters for Dream 7B in OpenClaw.}"

tokenizer_venv="${DREAM7B_TOKENIZER_VENV:-/mnt/nas/openclaw/runtimes/dream7b-tokenizer-venv}"
tokenizer_dir="${DREAM7B_TOKENIZER:-/mnt/nas/openclaw/models/dream7b/tokenizer}"
seq_len="${DREAM7B_BPU_SEQ_LEN:-16}"
min_mask_count="${DREAM7B_BPU_MIN_MASK_COUNT:-4}"
steps="${DREAM7B_BPU_DIFFUSION_STEPS:-2}"
top_k="${DREAM7B_BPU_TOP_K:-5}"
eps="${DREAM7B_BPU_EPS:-0.001}"
remasking="${DREAM7B_BPU_REMASKING:-entropy_exit}"
temperature="${DREAM7B_BPU_TEMP:-0}"
seed="${DREAM7B_BPU_SEED:-42}"
entropy_threshold="${DREAM7B_BPU_ENTROPY_THRESHOLD:-1.5}"

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
run_dir="$report_root/dream7b_bpu_diffusion_loop_$stamp"
mkdir -p "$run_dir"

"$tokenizer_venv/bin/python" - "$tokenizer_dir" "$prompt" "$run_dir" "$seq_len" "$min_mask_count" "$steps" "$top_k" "$eps" "$remasking" "$temperature" "$seed" "$entropy_threshold" <<'PY'
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
from transformers import AutoTokenizer

(
    tokenizer_dir,
    prompt,
    run_dir_text,
    seq_len_text,
    min_mask_count_text,
    steps_text,
    top_k_text,
    eps_text,
    remasking,
    temperature_text,
    seed_text,
    entropy_threshold_text,
) = sys.argv[1:13]
run_dir = Path(run_dir_text)
seq_len = int(seq_len_text)
min_mask_count = int(min_mask_count_text)
steps = int(steps_text)
top_k = int(top_k_text)
eps = float(eps_text)
temperature = float(temperature_text)
seed = int(seed_text)
entropy_threshold = float(entropy_threshold_text)
if min_mask_count <= 0 or min_mask_count >= seq_len:
    raise SystemExit(f"min_mask_count must be between 1 and seq_len-1, got {min_mask_count}")
if steps <= 0:
    raise SystemExit(f"steps must be positive, got {steps}")
if remasking not in {"low_confidence", "entropy_exit", "maskgit_plus", "topk_margin", "entropy"}:
    raise SystemExit(f"unsupported remasking strategy: {remasking}")

rng = np.random.default_rng(seed)


def softmax(values):
    shifted = values.astype(np.float64, copy=False) - float(np.max(values))
    exp = np.exp(shifted)
    return exp / float(np.sum(exp))


def sample_from_scores(scores):
    if temperature > 0:
        probs = softmax(scores / temperature)
        token_id = int(rng.choice(np.arange(scores.shape[0]), p=probs))
    else:
        probs = softmax(scores)
        token_id = int(np.argmax(scores))
    sorted_probs = np.sort(probs)[::-1]
    top1_prob = float(sorted_probs[0]) if sorted_probs.size else 0.0
    top2_prob = float(sorted_probs[1]) if sorted_probs.size > 1 else 0.0
    entropy = float(-np.sum(probs * np.log(probs + 1e-10)))
    if remasking == "topk_margin":
        confidence = top1_prob - top2_prob
    elif remasking in {"entropy", "entropy_exit"}:
        confidence = -entropy
    else:
        confidence = top1_prob
    return token_id, probs, confidence, entropy, top1_prob, top2_prob

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

tokens = prefix_ids + [mask_id] * (seq_len - len(prefix_ids))
if len(tokens) != seq_len:
    raise SystemExit(f"internal error: built {len(tokens)} tokens, expected {seq_len}")

timesteps = np.linspace(1.0, eps, steps + 1, dtype=np.float64)
history = []

for step in range(steps):
    mask_positions = [idx for idx, value in enumerate(tokens) if value == mask_id]
    if not mask_positions:
        break

    step_dir = run_dir / f"step_{step:02d}"
    forward_dir = step_dir / "forward"
    step_dir.mkdir(parents=True, exist_ok=True)
    tokens_bin = step_dir / "tokens.bin"
    np.asarray(tokens, dtype=np.int32).tofile(tokens_bin)

    cmd = [
        "dream7b-bpu-forward",
        "--tokens-bin", str(tokens_bin),
        "--output-dir", str(forward_dir),
        "--save-logits",
        "--top-k", str(top_k),
    ]
    proc = subprocess.run(cmd, text=True, capture_output=True)
    (step_dir / "forward.stdout").write_text(proc.stdout, encoding="utf-8")
    (step_dir / "forward.stderr").write_text(proc.stderr, encoding="utf-8")
    if proc.returncode != 0:
        raise SystemExit(f"step {step} BPU forward failed with rc={proc.returncode}: {step_dir}")

    logits_path = forward_dir / "logits.npy"
    logits = np.load(logits_path)
    shifted = np.concatenate([logits[:, :1, :], logits[:, :-1, :]], axis=1)

    candidates = []
    for pos in mask_positions:
        scores = shifted[0, pos].astype(np.float32, copy=False)
        token_id, probs, confidence, entropy, top1_prob, top2_prob = sample_from_scores(scores)
        k = min(max(top_k, 0), scores.shape[0])
        if k > 0:
            top_indices = np.argpartition(scores, -k)[-k:]
            top_indices = top_indices[np.argsort(scores[top_indices])[::-1]]
        else:
            top_indices = np.asarray([], dtype=np.int64)
        candidates.append({
            "position": int(pos),
            "selected_token_id": token_id,
            "selected_logit": float(scores[token_id]),
            "confidence": float(confidence),
            "entropy": float(entropy),
            "top1_probability": float(top1_prob),
            "top2_probability": float(top2_prob),
            "topk": [{"token_id": int(idx), "logit": float(scores[idx]), "probability": float(probs[idx])} for idx in top_indices],
        })

    t = timesteps[step]
    s = timesteps[step + 1]
    if step < steps - 1:
        transfer_count = int(len(mask_positions) * (1.0 - s / t))
        transfer_count = max(1, min(transfer_count, len(mask_positions)))
    else:
        transfer_count = len(mask_positions)

    if remasking == "entropy_exit" and step < steps - 1:
        eligible = [item for item in candidates if item["entropy"] <= entropy_threshold]
        if eligible:
            transfer_count = max(transfer_count, len(eligible))
            transfer_count = min(transfer_count, len(mask_positions))

    candidates.sort(key=lambda item: item["confidence"], reverse=True)
    transferred = candidates[:transfer_count]
    for item in transferred:
        tokens[item["position"]] = item["selected_token_id"]

    history.append({
        "step": step,
        "mask_positions_before": mask_positions,
        "transfer_count": transfer_count,
        "transferred": transferred,
        "forward_summary": str(forward_dir / "summary.json"),
        "logits_npy": str(logits_path),
        "tokens_after": list(tokens),
        "decoded_after": tok.decode(tokens, skip_special_tokens=True),
    })

remaining_masks = [idx for idx, value in enumerate(tokens) if value == mask_id]
verdict = "ok_dream7b_bpu_diffusion_loop_probe" if not remaining_masks else "partial_dream7b_bpu_diffusion_loop_probe"
summary = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": verdict,
    "prompt": prompt,
    "prepared_prompt": prepared,
    "seq_len": seq_len,
    "steps": steps,
    "eps": eps,
    "top_k": top_k,
    "remasking": remasking,
    "temperature": temperature,
    "seed": seed,
    "entropy_threshold": entropy_threshold,
    "fit_mode": fit_mode,
    "prompt_token_count": len(prompt_ids),
    "prefix_token_count": len(prefix_ids),
    "mask_token_id": mask_id,
    "initial_tokens": prefix_ids + [mask_id] * (seq_len - len(prefix_ids)),
    "final_tokens": tokens,
    "remaining_mask_positions": remaining_masks,
    "decoded_final": tok.decode(tokens, skip_special_tokens=True),
    "logits_shift": "dream_generation_cat_logits_first_then_previous_positions",
    "history": history,
    "notes": [
        "This is a bounded host-side Dream diffusion loop over S100P BPU logits.",
        "It implements probe-side remasking strategies compatible with diffuse-cli names: low_confidence, entropy_exit, maskgit_plus, topk_margin, entropy.",
        "It proves the multi-call BPU logits loop skeleton, but still needs production quality gates before replacing the CPU path.",
    ],
}
summary_json = run_dir / "summary.json"
summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

lines = [
    "# Dream 7B BPU Diffusion Loop Probe",
    "",
    f"- generated_at: {summary['generated_at']}",
    f"- verdict: {summary['verdict']}",
    f"- seq_len: {seq_len}",
    f"- steps: {steps}",
    f"- remasking: {remasking}",
    f"- temperature: {temperature}",
    f"- entropy_threshold: {entropy_threshold}",
    f"- prompt_token_count: {len(prompt_ids)}",
    f"- prefix_token_count: {len(prefix_ids)}",
    f"- remaining_mask_positions: {remaining_masks}",
    "",
    "## Step History",
    "",
    "| Step | Masks Before | Transfer Count | Transferred Token IDs | Confidences |",
    "| ---: | --- | ---: | --- | --- |",
]
for item in history:
    token_ids = [entry["selected_token_id"] for entry in item["transferred"]]
    confidences = [round(entry["confidence"], 6) for entry in item["transferred"]]
    lines.append(f"| {item['step']} | {item['mask_positions_before']} | {item['transfer_count']} | {token_ids} | {confidences} |")
lines.extend([
    "",
    "## Decoded Final",
    "",
    "```text",
    summary["decoded_final"],
    "```",
    "",
    "## Boundary",
    "",
    "- This is a bounded multi-step Dream diffusion bridge using S100P BPU logits.",
    "- It is a strategy-aware probe loop, not a fully accepted production text service.",
])
summary_md = run_dir / "summary.md"
summary_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(summary_md)
PY
