#!/usr/bin/env bash
set -euo pipefail

tokenizer_venv="${DREAM7B_TOKENIZER_VENV:-/mnt/nas/openclaw/runtimes/dream7b-tokenizer-venv}"
tokenizer_dir="${DREAM7B_TOKENIZER:-/mnt/nas/openclaw/models/dream7b/tokenizer}"
report_root="${DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_REPORT_ROOT:-/mnt/nas/openclaw/reports/models}"
run_dir_override="${DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_RUN_DIR:-}"
batch_count="${DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_BATCH_COUNT:-16}"
seq_len="${DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_SEQ_LEN:-16}"
min_mask_count="${DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_MIN_MASK_COUNT:-4}"
steps="${DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_STEPS:-2}"
top_k="${DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_TOP_K:-5}"
eps="${DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_EPS:-0.001}"
remasking="${DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_REMASKING:-entropy_exit}"
temperature="${DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_TEMP:-0}"
seed="${DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_SEED:-42}"
entropy_threshold="${DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_ENTROPY_THRESHOLD:-1.5}"
forward_cmd="${DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_FORWARD_CMD:-dream7b-bpu-fine-batch-forward}"
prompts_json=""
prompts_jsonl=""
prompt_args=()

usage() {
  cat >&2 <<'USAGE'
usage: dream7b-bpu-diffusion-batch-generate [--report-root DIR] [--run-dir DIR] [--batch-count N] [--seq-len 16] [--min-mask-count N] [--steps N] [--top-k N] [--eps FLOAT] [--remasking low_confidence|entropy_exit|maskgit_plus|topk_margin|entropy] [--temperature FLOAT] [--seed N] [--entropy-threshold FLOAT] [--forward-cmd CMD] [--prompts-json FILE|--prompts-jsonl FILE|--prompt TEXT ...]

Runs a bounded batched Dream 7B diffusion generation loop on S100P. Each
diffusion step writes tokens_batch.json, calls the configured BPU batch forward
command, and writes batch_generation.json plus batch_generation.md.
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
    --batch-count)
      [[ $# -ge 2 ]] || { usage; exit 2; }
      batch_count="$2"
      shift 2
      ;;
    --batch-count=*)
      batch_count="${1#--batch-count=}"
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
    --prompts-json)
      [[ $# -ge 2 ]] || { usage; exit 2; }
      prompts_json="$2"
      shift 2
      ;;
    --prompts-json=*)
      prompts_json="${1#--prompts-json=}"
      shift
      ;;
    --prompts-jsonl)
      [[ $# -ge 2 ]] || { usage; exit 2; }
      prompts_jsonl="$2"
      shift 2
      ;;
    --prompts-jsonl=*)
      prompts_jsonl="${1#--prompts-jsonl=}"
      shift
      ;;
    --prompt)
      [[ $# -ge 2 ]] || { usage; exit 2; }
      prompt_args+=("$2")
      shift 2
      ;;
    --prompt=*)
      prompt_args+=("${1#--prompt=}")
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
      prompt_args+=("$1")
      shift
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
for value_name in batch_count seq_len min_mask_count steps top_k seed; do
  value="${!value_name}"
  if ! [[ "$value" =~ ^[0-9]+$ ]]; then
    echo "$value_name must be a non-negative integer." >&2
    exit 2
  fi
done
if (( batch_count < 1 || batch_count > 16 )); then
  echo "DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_BATCH_COUNT must be between 1 and 16." >&2
  exit 2
fi
if (( seq_len != 16 )); then
  echo "DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_SEQ_LEN must be 16 for the current Dream 7B seq16 HBM artifacts." >&2
  exit 2
fi
if (( min_mask_count < 1 || min_mask_count >= seq_len )); then
  echo "DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_MIN_MASK_COUNT must be between 1 and seq_len-1." >&2
  exit 2
fi
if (( steps < 1 )); then
  echo "DREAM7B_BPU_DIFFUSION_BATCH_GENERATE_STEPS must be positive." >&2
  exit 2
fi
prompt_source_count=0
[[ -n "$prompts_json" ]] && prompt_source_count=$((prompt_source_count + 1))
[[ -n "$prompts_jsonl" ]] && prompt_source_count=$((prompt_source_count + 1))
[[ "${#prompt_args[@]}" -gt 0 ]] && prompt_source_count=$((prompt_source_count + 1))
if (( prompt_source_count > 1 )); then
  echo "Use only one prompt source: --prompts-json, --prompts-jsonl, or --prompt." >&2
  exit 2
fi
if [[ -n "$prompts_json" && ! -f "$prompts_json" ]]; then
  echo "Missing prompts JSON file: $prompts_json" >&2
  exit 2
fi
if [[ -n "$prompts_jsonl" && ! -f "$prompts_jsonl" ]]; then
  echo "Missing prompts JSONL file: $prompts_jsonl" >&2
  exit 2
fi

mkdir -p "$report_root"
stamp="$(date +%Y%m%d-%H%M%S)"
if [[ -n "$run_dir_override" ]]; then
  run_dir="$run_dir_override"
else
  run_dir="$report_root/dream7b_bpu_diffusion_batch_generate_$stamp"
fi
mkdir -p "$run_dir"

"$tokenizer_venv/bin/python" - "$tokenizer_dir" "$run_dir" "$batch_count" "$seq_len" "$min_mask_count" "$steps" "$top_k" "$eps" "$remasking" "$temperature" "$seed" "$entropy_threshold" "$forward_cmd" "$prompts_json" "$prompts_jsonl" "${prompt_args[@]}" <<'PY'
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
from transformers import AutoTokenizer

(
    tokenizer_dir,
    run_dir_text,
    batch_count_text,
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
    prompts_json,
    prompts_jsonl,
) = sys.argv[1:16]
prompt_args = sys.argv[16:]
run_dir = Path(run_dir_text)
batch_count = int(batch_count_text)
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


def load_prompts():
    if prompts_json:
        payload = json.loads(Path(prompts_json).read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError("--prompts-json must contain a JSON list")
        rows = []
        for item in payload:
            if isinstance(item, str):
                rows.append(item)
            elif isinstance(item, dict) and isinstance(item.get("prompt"), str):
                rows.append(item["prompt"])
            else:
                raise ValueError("--prompts-json entries must be strings or objects with a prompt string")
        return rows, prompts_json
    if prompts_jsonl:
        rows = []
        for line in Path(prompts_jsonl).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            if isinstance(item, str):
                rows.append(item)
            elif isinstance(item, dict) and isinstance(item.get("prompt"), str):
                rows.append(item["prompt"])
            else:
                raise ValueError("--prompts-jsonl lines must be strings or objects with a prompt string")
        return rows, prompts_jsonl
    if prompt_args:
        return prompt_args, "argv_prompt"
    defaults = [
        "hello",
        "Explain BPU in one sentence.",
        "List one robotics sensor.",
        "Write a short OpenClaw status.",
        "Name one NAS use case.",
        "Give one S100P deployment check.",
        "Summarize queue batching.",
        "Say why telemetry matters.",
        "Describe Dream diffusion.",
        "State one model boundary.",
        "Give a service health phrase.",
        "Name one log artifact.",
        "Mention HBM cache.",
        "Say batch generation.",
        "Write a concise diagnostic.",
        "Explain seq16 briefly.",
    ]
    return defaults[:batch_count], "built_in_defaults"


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


def logits_paths_from_summary(summary, expected_count):
    raw = summary.get("logits_npy") or ""
    paths = json.loads(raw) if raw.startswith("[") else [raw]
    if len(paths) != expected_count:
        raise ValueError(f"expected {expected_count} logits paths, got {len(paths)}: {paths}")
    return [Path(item) for item in paths]


tok = AutoTokenizer.from_pretrained(tokenizer_dir, trust_remote_code=True, local_files_only=True)
prompts, prompt_source = load_prompts()
if not prompts:
    raise SystemExit("prompt list is empty")
if len(prompts) > 16:
    raise SystemExit(f"prompt count exceeds current batch limit 16: {len(prompts)}")
if len(prompts) != batch_count:
    batch_count = len(prompts)

mask_id = int(tok.mask_token_id)
prefix_limit = seq_len - min_mask_count
samples = []
tokens_batch = []
for batch_index, prompt in enumerate(prompts):
    if prompt.startswith("<|im_start|>"):
        prepared = prompt
    else:
        prepared = f"<|im_start|>user\n{prompt}<|im_end|>\n<|im_start|>assistant\n"
    prompt_ids = tok.encode(prepared)
    if len(prompt_ids) >= seq_len:
        prefix_ids = prompt_ids[-prefix_limit:]
        fit_mode = "truncate_prompt_keep_min_masks"
    else:
        prefix_ids = prompt_ids
        fit_mode = "natural_prompt_then_masks"
    tokens = prefix_ids + [mask_id] * (seq_len - len(prefix_ids))
    if len(tokens) != seq_len:
        raise SystemExit(f"internal error: built {len(tokens)} tokens for batch {batch_index}, expected {seq_len}")
    samples.append({
        "batch_index": batch_index,
        "prompt": prompt,
        "prepared_prompt": prepared,
        "fit_mode": fit_mode,
        "prompt_token_count": len(prompt_ids),
        "prefix_token_count": len(prefix_ids),
        "initial_tokens": list(tokens),
        "tokens": tokens,
        "history": [],
    })
    tokens_batch.append(tokens)

timesteps = np.linspace(1.0, eps, steps + 1, dtype=np.float64)
history = []
forward_summary_payloads = []

for step in range(steps):
    active = [sample for sample in samples if any(value == mask_id for value in sample["tokens"])]
    if not active:
        break
    step_dir = run_dir / f"step_{step:02d}"
    forward_dir = step_dir / "forward"
    step_dir.mkdir(parents=True, exist_ok=True)
    tokens_batch_json = step_dir / "tokens_batch.json"
    tokens_snapshot = [sample["tokens"] for sample in samples]
    tokens_batch_json.write_text(json.dumps(tokens_snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    cmd = [
        forward_cmd,
        "--tokens-batch-json", str(tokens_batch_json),
        "--output-dir", str(forward_dir),
        "--save-logits",
        "--top-k", str(top_k),
    ]
    proc = subprocess.run(cmd, text=True, capture_output=True)
    (step_dir / "forward.stdout").write_text(proc.stdout, encoding="utf-8")
    (step_dir / "forward.stderr").write_text(proc.stderr, encoding="utf-8")
    if proc.returncode != 0:
        errors.append(f"step {step} BPU batch forward failed with rc={proc.returncode}: {step_dir}")
        break

    forward_summary_json = forward_dir / "summary.json"
    forward_summary = {}
    if forward_summary_json.is_file():
        forward_summary = json.loads(forward_summary_json.read_text(encoding="utf-8"))
        forward_summary_payloads.append(forward_summary)
    else:
        errors.append(f"missing forward summary: {forward_summary_json}")
        break

    if forward_summary.get("batch_count") != batch_count:
        errors.append(f"unexpected forward batch_count at step {step}: {forward_summary.get('batch_count')}")
    logits_paths = logits_paths_from_summary(forward_summary, batch_count)
    step_samples = []
    for sample in samples:
        batch_index = sample["batch_index"]
        tokens = sample["tokens"]
        mask_positions = [idx for idx, value in enumerate(tokens) if value == mask_id]
        if not mask_positions:
            sample_step = {
                "batch_index": batch_index,
                "mask_positions_before": [],
                "transfer_count": 0,
                "transferred": [],
                "tokens_after": list(tokens),
                "decoded_after": tok.decode(tokens, skip_special_tokens=True),
            }
            step_samples.append(sample_step)
            sample["history"].append({"step": step, **sample_step})
            continue

        logits_path = logits_paths[batch_index]
        if not logits_path.is_file():
            errors.append(f"missing logits path at step {step} batch {batch_index}: {logits_path}")
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
        sample_step = {
            "batch_index": batch_index,
            "mask_positions_before": mask_positions,
            "transfer_count": transfer_count,
            "transferred": transferred,
            "tokens_after": list(tokens),
            "decoded_after": tok.decode(tokens, skip_special_tokens=True),
        }
        step_samples.append(sample_step)
        sample["history"].append({"step": step, **sample_step})
    else:
        history.append({
            "step": step,
            "tokens_batch_json": str(tokens_batch_json),
            "forward_summary": str(forward_summary_json),
            "forward_verdict": forward_summary.get("verdict"),
            "forward_execution_mode": forward_summary.get("execution_mode"),
            "forward_window_execution_mode": forward_summary.get("window_execution_mode"),
            "forward_child_process_count": forward_summary.get("child_process_count"),
            "forward_batch_count": forward_summary.get("batch_count"),
            "forward_final_shapes": forward_summary.get("final_shapes"),
            "forward_logits_npy": forward_summary.get("logits_npy"),
            "samples": step_samples,
        })
        continue
    break

remaining_by_batch = []
decoded_by_batch = []
sample_payloads = []
for sample in samples:
    tokens = sample["tokens"]
    remaining = [idx for idx, value in enumerate(tokens) if value == mask_id]
    remaining_by_batch.append({"batch_index": sample["batch_index"], "remaining_mask_positions": remaining})
    decoded = tok.decode(tokens, skip_special_tokens=True)
    decoded_by_batch.append({"batch_index": sample["batch_index"], "prompt": sample["prompt"], "decoded_final": decoded})
    sample_payloads.append({
        "batch_index": sample["batch_index"],
        "prompt": sample["prompt"],
        "prepared_prompt": sample["prepared_prompt"],
        "fit_mode": sample["fit_mode"],
        "prompt_token_count": sample["prompt_token_count"],
        "prefix_token_count": sample["prefix_token_count"],
        "initial_tokens": sample["initial_tokens"],
        "final_tokens": list(tokens),
        "remaining_mask_positions": remaining,
        "decoded_final": decoded,
        "history": sample["history"],
    })
for item in history:
    if item.get("forward_verdict") != "ok_dream7b_segmented_hbm_python_forward":
        errors.append(f"unexpected forward_verdict at step {item['step']}: {item.get('forward_verdict')}")
    if item.get("forward_execution_mode") != "pair_window_batch":
        errors.append(f"unexpected forward_execution_mode at step {item['step']}: {item.get('forward_execution_mode')}")
    if item.get("forward_window_execution_mode") != "window-batch":
        errors.append(f"unexpected forward_window_execution_mode at step {item['step']}: {item.get('forward_window_execution_mode')}")
    if item.get("forward_child_process_count") != 0:
        errors.append(f"unexpected forward_child_process_count at step {item['step']}: {item.get('forward_child_process_count')}")
    if item.get("forward_batch_count") != batch_count:
        errors.append(f"unexpected forward_batch_count at step {item['step']}: {item.get('forward_batch_count')}")
    if item.get("forward_final_shapes") != [[1, seq_len, 152064] for _ in range(batch_count)]:
        errors.append(f"unexpected forward_final_shapes at step {item['step']}: {item.get('forward_final_shapes')}")
if any(item["remaining_mask_positions"] for item in remaining_by_batch):
    errors.append(f"remaining masks after batch generation: {remaining_by_batch}")

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_bpu_diffusion_batch_generate" if not errors else "failed_dream7b_bpu_diffusion_batch_generate",
    "run_dir": str(run_dir),
    "tokenizer_dir": tokenizer_dir,
    "prompt_source": prompt_source,
    "batch_count": batch_count,
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
    "mask_token_id": mask_id,
    "remaining_mask_positions_by_batch": remaining_by_batch,
    "decoded_final_by_batch": decoded_by_batch,
    "samples": sample_payloads,
    "history": history,
    "forward_summary_count": len(forward_summary_payloads),
    "forward_batch_counts": [item.get("batch_count") for item in forward_summary_payloads],
    "logits_shift": "dream_generation_cat_logits_first_then_previous_positions",
    "boundary": "bounded_seq16_batch_generation_entrypoint_not_complete_production_text_service",
    "errors": errors,
}
json_path = run_dir / "batch_generation.json"
json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

lines = [
    "# Dream 7B BPU Diffusion Batch Generate",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- run_dir: {payload['run_dir']}",
    f"- tokenizer_dir: {payload['tokenizer_dir']}",
    f"- prompt_source: {payload['prompt_source']}",
    f"- batch_count: {payload['batch_count']}",
    f"- seq_len: {payload['seq_len']}",
    f"- steps: {payload['steps']}",
    f"- executed_step_count: {payload['executed_step_count']}",
    f"- remasking: {payload['remasking']}",
    f"- forward_cmd: {payload['forward_cmd']}",
    f"- temperature: {payload['temperature']}",
    f"- entropy_threshold: {payload['entropy_threshold']}",
    f"- remaining_mask_positions_by_batch: {payload['remaining_mask_positions_by_batch']}",
    "",
    "## Step History",
    "",
    "| Step | Forward Batch Count | Forward Shape Count | Forward Mode |",
    "| ---: | ---: | ---: | --- |",
]
for item in history:
    lines.append(
        f"| {item['step']} | {item['forward_batch_count']} | {len(item.get('forward_final_shapes') or [])} | {item['forward_execution_mode']} / {item['forward_window_execution_mode']} |"
    )
lines.extend([
    "",
    "## Decoded Final By Batch",
    "",
    "| Batch | Prompt | Decoded Final |",
    "| ---: | --- | --- |",
])
for item in decoded_by_batch:
    decoded = str(item["decoded_final"]).replace("\n", "\\n")
    prompt = str(item["prompt"]).replace("\n", "\\n")
    lines.append(f"| {item['batch_index']} | {prompt} | {decoded} |")
error_lines = [f"- {item}" for item in errors] if errors else ["- none"]
lines.extend([
    "",
    "## Errors",
    "",
    *error_lines,
    "",
    "## Boundary",
    "",
    "- This is a bounded seq16 batch Dream diffusion generation entrypoint using S100P BPU batch logits.",
    "- It is not a complete production text service.",
])
md_path = run_dir / "batch_generation.md"
md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(md_path)
if errors:
    raise SystemExit("; ".join(errors))
PY
