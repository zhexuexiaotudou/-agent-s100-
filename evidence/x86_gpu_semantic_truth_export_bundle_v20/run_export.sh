#!/usr/bin/env bash
set -euo pipefail
MODEL_DIR=${1:?usage: ./run_export.sh /path/to/dream7b-hf [out_dir]}
OUT_DIR=${2:-semantic_truth_output}
python3 export_semantic_truth.py --model-dir "$MODEL_DIR" --cases-jsonl semantic_cases.jsonl --output-root "$OUT_DIR" --dtype bfloat16 --device auto --fallback-fp32
