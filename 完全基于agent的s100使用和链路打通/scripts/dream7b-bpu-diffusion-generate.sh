#!/usr/bin/env bash
set -euo pipefail

tokenizer_venv="${DREAM7B_TOKENIZER_VENV:-/mnt/nas/openclaw/runtimes/dream7b-tokenizer-venv}"
tokenizer_dir="${DREAM7B_TOKENIZER:-/mnt/nas/openclaw/models/dream7b/tokenizer}"
report_root="${DREAM7B_BPU_DIFFUSION_GENERATE_REPORT_ROOT:-/mnt/nas/openclaw/reports/models}"
run_dir_override="${DREAM7B_BPU_DIFFUSION_GENERATE_RUN_DIR:-}"
seq_len="${DREAM7B_BPU_DIFFUSION_GENERATE_SEQ_LEN:-16}"
min_mask_count="${DREAM7B_BPU_DIFFUSION_GENERATE_MIN_MASK_COUNT:-4}"
steps="${DREAM7B_BPU_DIFFUSION_GENERATE_STEPS:-2}"
top_k="${DREAM7B_BPU_DIFFUSION_GENERATE_TOP_K:-5}"
eps="${DREAM7B_BPU_DIFFUSION_GENERATE_EPS:-0.001}"
remasking="${DREAM7B_BPU_DIFFUSION_GENERATE_REMASKING:-entropy_exit}"
temperature="${DREAM7B_BPU_DIFFUSION_GENERATE_TEMP:-0}"
seed="${DREAM7B_BPU_DIFFUSION_GENERATE_SEED:-42}"
entropy_threshold="${DREAM7B_BPU_DIFFUSION_GENERATE_ENTROPY_THRESHOLD:-1.5}"
forward_cmd="${DREAM7B_BPU_DIFFUSION_GENERATE_FORWARD_CMD:-dream7b-bpu-fine-forward}"
prompt_file=""
prompt_text=""

usage() {
  cat >&2 <<'USAGE'
usage: dream7b-bpu-diffusion-generate [--report-root DIR] [--run-dir DIR] [--seq-len 16] [--min-mask-count N] [--steps N] [--top-k N] [--eps FLOAT] [--remasking low_confidence|entropy_exit|maskgit_plus|topk_margin|entropy] [--temperature FLOAT] [--seed N] [--entropy-threshold FLOAT] [--forward-cmd CMD] [--prompt TEXT|--prompt-file FILE] [--] prompt text

Runs a bounded Dream 7B diffusion generation loop on S100P. The command uses
Dream 7B tokenizer input, calls the configured BPU forward command for each
diffusion step, and writes generation.json plus generation.md.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --report-root)
      [[ $# -ge 2 ]] || { usage; exit 2; }
      report_root="$2"
      shift 2
      ;;
    --report-root=*)
      report_root="${1#--report-root=}"
      shift
      ;;
    --run-dir)
      [[ $# -ge 2 ]] || { usage; exit 2; }
      run_dir_override="$2"
      shift 2
      ;;
    --run-dir=*)
      run_dir_override="${1#--run-dir=}"
      shift
      ;;
    --seq-len)
      [[ $# -ge 2 ]] || { usage; exit 2; }
      seq_len="$2"
      shift 2
      ;;
    --seq-len=*)
      seq_len="${1#--seq-len=}"
      shift
      ;;
    --min-mask-count)
      [[ $# -ge 2 ]] || { usage; exit 2; }
      min_mask_count="$2"
      shift 2
      ;;
    --min-mask-count=*)
      min_mask_count="${1#--min-mask-count=}"
      shift
      ;;
    --steps)
      [[ $# -ge 2 ]] || { usage; exit 2; }
      steps="$2"
      shift 2
      ;;
    --steps=*)
      steps="${1#--steps=}"
      shift
      ;;
    --top-k)
      [[ $# -ge 2 ]] || { usage; exit 2; }
      top_k="$2"
      shift 2
      ;;
    --top-k=*)
      top_k="${1#--top-k=}"
      shift
      ;;
    --eps)
      [[ $# -ge 2 ]] || { usage; exit 2; }
      eps="$2"
      shift 2
      ;;
    --eps=*)
      eps="${1#--eps=}"
      shift
      ;;
    --remasking)
      [[ $# -ge 2 ]] || { usage; exit 2; }
      remasking="$2"
      shift 2
      ;;
    --remasking=*)
      remasking="${1#--remasking=}"
      shift
      ;;
    --temperature)
      [[ $# -ge 2 ]] || { usage; exit 2; }
      temperature="$2"
      shift 2
      ;;
    --temperature=*)
      temperature="${1#--temperature=}"
      shift
      ;;
    --seed)
      [[ $# -ge 2 ]] || { usage; exit 2; }
      seed="$2"
      shift 2
      ;;
    --seed=*)
      seed="${1#--seed=}"
      shift
      ;;
    --entropy-threshold)
      [[ $# -ge 2 ]] || { usage; exit 2; }
      entropy_threshold="$2"
      shift 2
      ;;
    --entropy-threshold=*)
      entropy_threshold="${1#--entropy-threshold=}"
      shift
      ;;
    --forward-cmd)
      [[ $# -ge 2 ]] || { usage; exit 2; }
      forward_cmd="$2"
      shift 2
      ;;
    --forward-cmd=*)
      forward_cmd="${1#--forward-cmd=}"
      shift
      ;;
    --prompt)
      [[ $# -ge 2 ]] || { usage; exit 2; }
      prompt_text="$2"
      shift 2
      ;;
    --prompt=*)
      prompt_text="${1#--prompt=}"
      shift
      ;;
    --prompt-file)
      [[ $# -ge 2 ]] || { usage; exit 2; }
      prompt_file="$2"
      shift 2
      ;;
    --prompt-file=*)
      prompt_file="${1#--prompt-file=}"
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    --)
      shift
      break
      ;;
    *)
      break
      ;;
  esac
done

case "$report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_root" >&2
    exit 2
    ;;
esac
if [[ -n "$run_dir_override" ]]; then
  case "$run_dir_override" in
    /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
    *)
      echo "Refusing run path outside approved report directories: $run_dir_override" >&2
      exit 2
      ;;
  esac
fi
if [[ ! -x "$tokenizer_venv/bin/python" ]]; then
  echo "Missing Dream 7B tokenizer venv: $tokenizer_venv" >&2
  exit 4
fi
if [[ ! -d "$tokenizer_dir" ]]; then
  echo "Missing Dream 7B tokenizer directory: $tokenizer_dir" >&2
  exit 4
fi
if ! command -v "$forward_cmd" >/dev/null 2>&1; then
  echo "Missing deployed S100P command: $forward_cmd" >&2
  exit 4
fi
case "$remasking" in
  low_confidence|entropy_exit|maskgit_plus|topk_margin|entropy) ;;
  *)
    echo "unsupported remasking strategy: $remasking" >&2
    exit 2
    ;;
esac
for value_name in seq_len min_mask_count steps top_k seed; do
  value="${!value_name}"
  if ! [[ "$value" =~ ^[0-9]+$ ]]; then
    echo "$value_name must be a non-negative integer." >&2
    exit 2
  fi
done
if (( seq_len != 16 )); then
  echo "DREAM7B_BPU_DIFFUSION_GENERATE_SEQ_LEN must be 16 for the current Dream 7B seq16 HBM artifacts." >&2
  exit 2
fi
if (( min_mask_count < 1 || min_mask_count >= seq_len )); then
  echo "DREAM7B_BPU_DIFFUSION_GENERATE_MIN_MASK_COUNT must be between 1 and seq_len-1." >&2
  exit 2
fi
if (( steps < 1 )); then
  echo "DREAM7B_BPU_DIFFUSION_GENERATE_STEPS must be positive." >&2
  exit 2
fi

if [[ -n "$prompt_file" && -n "$prompt_text" ]]; then
  echo "Use either --prompt or --prompt-file, not both." >&2
  exit 2
fi
if [[ -n "$prompt_file" ]]; then
  if [[ ! -f "$prompt_file" ]]; then
    echo "Missing prompt file: $prompt_file" >&2
    exit 2
  fi
  prompt_text="$(cat "$prompt_file")"
fi
if [[ -z "$prompt_text" ]]; then
  prompt_text="$*"
fi
if [[ -z "$prompt_text" && ! -t 0 ]]; then
  prompt_text="$(cat)"
fi
if [[ -z "$prompt_text" ]]; then
  usage
  exit 2
fi

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
if [[ -n "$run_dir_override" ]]; then
  run_dir="$run_dir_override"
else
  run_dir="$report_root/dream7b_bpu_diffusion_generate_$stamp"
fi
mkdir -p "$run_dir"

"$tokenizer_venv/bin/python" - "$tokenizer_dir" "$prompt_text" "$run_dir" "$seq_len" "$min_mask_count" "$steps" "$top_k" "$eps" "$remasking" "$temperature" "$seed" "$entropy_threshold" "$forward_cmd" <<'PY'
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
    forward_cmd,
) = sys.argv[1:14]
run_dir = Path(run_dir_text)
seq_len = int(seq_len_text)
min_mask_count = int(min_mask_count_text)
steps = int(steps_text)
top_k = int(top_k_text)
eps = float(eps_text)
temperature = float(temperature_text)
seed = int(seed_text)
entropy_threshold = float(entropy_threshold_text)
rng = np.random.default_rng(seed)
errors = []


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

initial_tokens = list(tokens)
timesteps = np.linspace(1.0, eps, steps + 1, dtype=np.float64)
history = []
forward_summary_payloads = []

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
        forward_cmd,
        "--tokens-bin", str(tokens_bin),
        "--output-dir", str(forward_dir),
        "--save-logits",
        "--top-k", str(top_k),
    ]
    proc = subprocess.run(cmd, text=True, capture_output=True)
    (step_dir / "forward.stdout").write_text(proc.stdout, encoding="utf-8")
    (step_dir / "forward.stderr").write_text(proc.stderr, encoding="utf-8")
    if proc.returncode != 0:
        errors.append(f"step {step} BPU forward failed with rc={proc.returncode}: {step_dir}")
        break

    forward_summary_json = forward_dir / "summary.json"
    forward_summary = {}
    if forward_summary_json.is_file():
        forward_summary = json.loads(forward_summary_json.read_text(encoding="utf-8"))
        forward_summary_payloads.append(forward_summary)
    else:
        errors.append(f"missing forward summary: {forward_summary_json}")

    logits_path = forward_dir / "logits.npy"
    if not logits_path.is_file():
        errors.append(f"missing logits.npy: {logits_path}")
        break
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
            "selected_token_text": tok.decode([token_id], skip_special_tokens=False),
            "selected_logit": float(scores[token_id]),
            "confidence": float(confidence),
            "entropy": float(entropy),
            "top1_probability": float(top1_prob),
            "top2_probability": float(top2_prob),
            "topk": [
                {
                    "token_id": int(idx),
                    "token_text": tok.decode([int(idx)], skip_special_tokens=False),
                    "logit": float(scores[idx]),
                    "probability": float(probs[idx]),
                }
                for idx in top_indices
            ],
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
        "forward_summary": str(forward_summary_json),
        "forward_verdict": forward_summary.get("verdict"),
        "forward_execution_mode": forward_summary.get("execution_mode"),
        "forward_window_execution_mode": forward_summary.get("window_execution_mode"),
        "forward_child_process_count": forward_summary.get("child_process_count"),
        "forward_final_shape": forward_summary.get("final_shape"),
        "logits_npy": str(logits_path),
        "tokens_after": list(tokens),
        "decoded_after": tok.decode(tokens, skip_special_tokens=True),
    })

remaining_masks = [idx for idx, value in enumerate(tokens) if value == mask_id]
for item in history:
    if item.get("forward_verdict") != "ok_dream7b_segmented_hbm_python_forward":
        errors.append(f"unexpected forward_verdict at step {item['step']}: {item.get('forward_verdict')}")
    if item.get("forward_execution_mode") != "pair_in_process":
        errors.append(f"unexpected forward_execution_mode at step {item['step']}: {item.get('forward_execution_mode')}")
    if item.get("forward_window_execution_mode") != "in-process":
        errors.append(f"unexpected forward_window_execution_mode at step {item['step']}: {item.get('forward_window_execution_mode')}")
    if item.get("forward_child_process_count") != 0:
        errors.append(f"unexpected forward_child_process_count at step {item['step']}: {item.get('forward_child_process_count')}")
    if item.get("forward_final_shape") != [1, seq_len, 152064]:
        errors.append(f"unexpected forward_final_shape at step {item['step']}: {item.get('forward_final_shape')}")
if remaining_masks:
    errors.append(f"remaining masks after generation: {remaining_masks}")

decoded_final = tok.decode(tokens, skip_special_tokens=True)
payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_bpu_diffusion_generate" if not errors else "failed_dream7b_bpu_diffusion_generate",
    "run_dir": str(run_dir),
    "tokenizer_dir": tokenizer_dir,
    "prompt": prompt,
    "prepared_prompt": prepared,
    "seq_len": seq_len,
    "steps": steps,
    "executed_step_count": len(history),
    "eps": eps,
    "top_k": top_k,
    "remasking": remasking,
    "temperature": temperature,
    "seed": seed,
    "entropy_threshold": entropy_threshold,
    "forward_cmd": forward_cmd,
    "fit_mode": fit_mode,
    "prompt_token_count": len(prompt_ids),
    "prefix_token_count": len(prefix_ids),
    "mask_token_id": mask_id,
    "initial_tokens": initial_tokens,
    "final_tokens": tokens,
    "remaining_mask_positions": remaining_masks,
    "decoded_final": decoded_final,
    "history": history,
    "forward_summary_count": len(forward_summary_payloads),
    "logits_shift": "dream_generation_cat_logits_first_then_previous_positions",
    "boundary": "bounded_seq16_generation_entrypoint_not_complete_production_text_service",
    "errors": errors,
}
json_path = run_dir / "generation.json"
json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

lines = [
    "# Dream 7B BPU Diffusion Generate",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- run_dir: {payload['run_dir']}",
    f"- tokenizer_dir: {payload['tokenizer_dir']}",
    f"- seq_len: {payload['seq_len']}",
    f"- steps: {payload['steps']}",
    f"- executed_step_count: {payload['executed_step_count']}",
    f"- remasking: {payload['remasking']}",
    f"- forward_cmd: {payload['forward_cmd']}",
    f"- temperature: {payload['temperature']}",
    f"- entropy_threshold: {payload['entropy_threshold']}",
    f"- prompt_token_count: {payload['prompt_token_count']}",
    f"- prefix_token_count: {payload['prefix_token_count']}",
    f"- remaining_mask_positions: {payload['remaining_mask_positions']}",
    "",
    "## Step History",
    "",
    "| Step | Masks Before | Transfer Count | Transferred Token IDs | Transferred Token Text | Forward Shape |",
    "| ---: | --- | ---: | --- | --- | --- |",
]
for item in history:
    token_ids = [entry["selected_token_id"] for entry in item["transferred"]]
    token_texts = [entry["selected_token_text"] for entry in item["transferred"]]
    lines.append(
        f"| {item['step']} | {item['mask_positions_before']} | {item['transfer_count']} | {token_ids} | {token_texts} | {item['forward_final_shape']} |"
    )
error_lines = [f"- {item}" for item in errors] if errors else ["- none"]
lines.extend([
    "",
    "## Decoded Final",
    "",
    "```text",
    decoded_final,
    "```",
    "",
    "## Errors",
    "",
    *error_lines,
    "",
    "## Boundary",
    "",
    "- This is a bounded seq16 Dream diffusion generation entrypoint using S100P BPU logits.",
    "- It is not a complete production text service.",
])
md_path = run_dir / "generation.md"
md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(md_path)
if errors:
    raise SystemExit("; ".join(errors))
PY
