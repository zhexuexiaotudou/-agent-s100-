#!/usr/bin/env bash
set -euo pipefail

tokenizer_venv="${DREAM7B_TOKENIZER_VENV:-/mnt/nas/openclaw/runtimes/dream7b-tokenizer-venv}"
tokenizer_dir="${DREAM7B_TOKENIZER:-/mnt/nas/openclaw/models/dream7b/tokenizer}"
seq_len="${DREAM7B_BPU_SEQ_LEN:-16}"
fit_mode="${DREAM7B_BPU_PROMPT_FIT:-exact}"
forward_args=()

usage() {
  cat >&2 <<'USAGE'
usage: dream7b-bpu-text-forward [--fit exact|truncate-left|pad-right] [--save-logits] [--top-k N] [--output-dir DIR] [--] prompt text

Encodes a Dream 7B prompt locally on S100P, then runs dream7b-bpu-forward.
Current HBM artifacts are compiled for seq16, so exact token length is the
default. Use --fit explicitly if a probe should truncate or pad.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --fit)
      [[ $# -ge 2 ]] || { usage; exit 2; }
      fit_mode="$2"
      shift 2
      ;;
    --fit=*)
      fit_mode="${1#--fit=}"
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    --save-logits)
      forward_args+=("$1")
      shift
      ;;
    --output-dir|--hbm-dir|--top-k)
      [[ $# -ge 2 ]] || { usage; exit 2; }
      forward_args+=("$1" "$2")
      shift 2
      ;;
    --output-dir=*|--hbm-dir=*)
      forward_args+=("$1")
      shift
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

if [[ ! -x "$tokenizer_venv/bin/python" ]]; then
  echo "Missing Dream 7B tokenizer venv: $tokenizer_venv" >&2
  exit 4
fi

if [[ ! -d "$tokenizer_dir" ]]; then
  echo "Missing Dream 7B tokenizer directory: $tokenizer_dir" >&2
  exit 4
fi

prompt="$*"
if [[ -z "$prompt" ]]; then
  prompt="$(cat)"
fi
if [[ -z "$prompt" ]]; then
  usage
  exit 2
fi

tokens="$("$tokenizer_venv/bin/python" - "$tokenizer_dir" "$seq_len" "$fit_mode" "$prompt" <<'PY'
import sys

from transformers import AutoTokenizer

tokenizer_dir, seq_len_text, fit_mode, prompt = sys.argv[1:5]
seq_len = int(seq_len_text)
tok = AutoTokenizer.from_pretrained(tokenizer_dir, trust_remote_code=True, local_files_only=True)

if prompt.startswith("<|im_start|>"):
    prepared = prompt
else:
    prepared = f"<|im_start|>user\n{prompt}<|im_end|>\n<|im_start|>assistant\n"

ids = tok.encode(prepared)
original_len = len(ids)

if fit_mode == "exact":
    if original_len != seq_len:
        raise SystemExit(f"prompt encoded to {original_len} tokens, expected exactly {seq_len}; use --fit truncate-left or --fit pad-right for probes")
elif fit_mode == "truncate-left":
    ids = ids[-seq_len:]
elif fit_mode == "pad-right":
    ids = ids[:seq_len] + [0] * max(0, seq_len - len(ids))
    ids = ids[:seq_len]
else:
    raise SystemExit(f"unsupported fit mode: {fit_mode}")

if len(ids) != seq_len:
    raise SystemExit(f"fit mode {fit_mode} produced {len(ids)} tokens, expected {seq_len}")

print(",".join(str(x) for x in ids))
PY
)"

exec dream7b-bpu-forward --tokens "$tokens" "${forward_args[@]}"
