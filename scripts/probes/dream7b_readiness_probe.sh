#!/usr/bin/env bash
set -euo pipefail

report_dir="${1:-/mnt/nas/openclaw/reports/models}"

case "$report_dir" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_dir" >&2
    exit 2
    ;;
esac

mkdir -p "$report_dir"
stamp="$(date +%Y%m%d-%H%M%S)"
report="$report_dir/dream7b_readiness_$stamp.md"
json="$report_dir/dream7b_readiness_$stamp.json"

cmd_status() {
  command -v "$1" >/dev/null 2>&1 && echo yes || echo no
}

python_module_status() {
  python3 - "$1" <<'PY' >/dev/null 2>&1 && echo yes || echo no
import importlib.util
import sys
print("yes" if importlib.util.find_spec(sys.argv[1]) else "no")
PY
}

count_matching_files() {
  local dir="$1"
  if [[ ! -d "$dir" ]]; then
    echo 0
    return
  fi
  find "$dir" -maxdepth 5 -type f \( \
    -iname '*dream*' -o -iname '*7b*' -o -iname '*.gguf' -o -iname '*.safetensors' -o \
    -iname '*.bin' -o -iname '*.onnx' -o -iname '*.pt' -o -iname '*.pth' \
  \) 2>/dev/null | wc -l | tr -d ' '
}

list_matching_files() {
  local dir="$1"
  if [[ ! -d "$dir" ]]; then
    return
  fi
  find "$dir" -maxdepth 5 -type f \( \
    -iname '*dream*' -o -iname '*7b*' -o -iname '*.gguf' -o -iname '*.safetensors' -o \
    -iname '*.bin' -o -iname '*.onnx' -o -iname '*.pt' -o -iname '*.pth' \
  \) -printf '%p\t%s bytes\n' 2>/dev/null | sort | head -40
}

python3_available="$(cmd_status python3)"
node_available="$(cmd_status node)"
llama_cli_available="$(cmd_status llama-cli)"
llama_cpp_available="$(cmd_status llama.cpp)"
llama_server_available="$(cmd_status llama-server)"
ollama_available="$(cmd_status ollama)"
vllm_available="$(cmd_status vllm)"

torch_available="$(python_module_status torch)"
transformers_available="$(python_module_status transformers)"
accelerate_available="$(python_module_status accelerate)"
sentencepiece_available="$(python_module_status sentencepiece)"
llama_cpp_python_available="$(python_module_status llama_cpp)"

model_dirs=(
  "/mnt/nas/openclaw/models"
  "/root/.openclaw/workspace/models"
  "/home/sunrise/models"
)

model_file_count=0
dream_named_count=0
model_dir_lines=""
model_file_lines=""
for dir in "${model_dirs[@]}"; do
  if [[ -d "$dir" ]]; then
    count="$(count_matching_files "$dir")"
    dream_count="$(find "$dir" -maxdepth 5 -type f \( -iname '*dream*' -o -iname '*Dream*' \) 2>/dev/null | wc -l | tr -d ' ')"
    model_file_count=$((model_file_count + count))
    dream_named_count=$((dream_named_count + dream_count))
    model_dir_lines+="$dir: $count candidate files, $dream_count dream-named files"$'\n'
    files="$(list_matching_files "$dir")"
    if [[ -n "$files" ]]; then
      model_file_lines+="$files"$'\n'
    fi
  else
    model_dir_lines+="$dir: missing"$'\n'
  fi
done

mem_total_gib="$(awk '/MemTotal:/ {printf "%.1f", $2/1024/1024}' /proc/meminfo 2>/dev/null || echo unknown)"
mem_available_gib="$(awk '/MemAvailable:/ {printf "%.1f", $2/1024/1024}' /proc/meminfo 2>/dev/null || echo unknown)"
swap_total_gib="$(awk '/SwapTotal:/ {printf "%.1f", $2/1024/1024}' /proc/meminfo 2>/dev/null || echo unknown)"
arch="$(uname -m 2>/dev/null || echo unknown)"
hostname_value="$(hostname 2>/dev/null || echo unknown)"

runtime_candidates=()
[[ "$llama_cli_available" == "yes" || "$llama_server_available" == "yes" || "$llama_cpp_python_available" == "yes" ]] && runtime_candidates+=("llama.cpp")
[[ "$ollama_available" == "yes" ]] && runtime_candidates+=("ollama")
[[ "$vllm_available" == "yes" ]] && runtime_candidates+=("vllm")
[[ "$torch_available" == "yes" && "$transformers_available" == "yes" ]] && runtime_candidates+=("torch-transformers")

runtime_summary="none"
if [[ ${#runtime_candidates[@]} -gt 0 ]]; then
  runtime_summary="$(printf '%s\n' "${runtime_candidates[@]}" | paste -sd ',' -)"
fi

verdict="blocked_no_model_and_runtime"
if [[ "$model_file_count" -gt 0 && "$runtime_summary" != "none" ]]; then
  verdict="candidate_runtime_and_model_present"
elif [[ "$model_file_count" -gt 0 ]]; then
  verdict="blocked_no_runtime"
elif [[ "$runtime_summary" != "none" ]]; then
  verdict="blocked_no_model"
fi

python3 - "$json" \
  "$report" "$hostname_value" "$arch" "$mem_total_gib" "$mem_available_gib" "$swap_total_gib" \
  "$python3_available" "$node_available" "$llama_cli_available" "$llama_server_available" \
  "$ollama_available" "$vllm_available" "$torch_available" "$transformers_available" \
  "$accelerate_available" "$sentencepiece_available" "$llama_cpp_python_available" \
  "$model_file_count" "$dream_named_count" "$runtime_summary" "$verdict" <<'PY'
import json
import sys
from datetime import datetime, timezone

(
    path, report, hostname, arch, mem_total_gib, mem_available_gib, swap_total_gib,
    python3_available, node_available, llama_cli_available, llama_server_available,
    ollama_available, vllm_available, torch_available, transformers_available,
    accelerate_available, sentencepiece_available, llama_cpp_python_available,
    model_file_count, dream_named_count, runtime_summary, verdict,
) = sys.argv[1:]

payload = {
    "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
    "mode": "read-only Dream 7B / local DLM deployment readiness",
    "report": report,
    "host": {"hostname": hostname, "arch": arch},
    "memory_gib": {
        "total": mem_total_gib,
        "available": mem_available_gib,
        "swap_total": swap_total_gib,
    },
    "commands": {
        "python3": python3_available == "yes",
        "node": node_available == "yes",
        "llama-cli": llama_cli_available == "yes",
        "llama-server": llama_server_available == "yes",
        "ollama": ollama_available == "yes",
        "vllm": vllm_available == "yes",
    },
    "python_modules": {
        "torch": torch_available == "yes",
        "transformers": transformers_available == "yes",
        "accelerate": accelerate_available == "yes",
        "sentencepiece": sentencepiece_available == "yes",
        "llama_cpp": llama_cpp_python_available == "yes",
    },
    "model_file_count": int(model_file_count),
    "dream_named_file_count": int(dream_named_count),
    "runtime_summary": runtime_summary,
    "verdict": verdict,
}

with open(path, "w", encoding="utf-8") as fh:
    json.dump(payload, fh, ensure_ascii=False, indent=2)
    fh.write("\n")
PY

{
  echo "# Dream 7B / Local DLM Readiness"
  echo
  echo "- generated_at: $(date -Is)"
  echo "- mode: read-only Dream 7B / local DLM deployment readiness"
  echo "- report: $report"
  echo "- json: $json"
  echo "- verdict: $verdict"
  echo
  echo "## Host And Memory"
  echo
  echo "| Check | Value |"
  echo "| --- | --- |"
  echo "| Hostname | $hostname_value |"
  echo "| Architecture | $arch |"
  echo "| Memory total GiB | $mem_total_gib |"
  echo "| Memory available GiB | $mem_available_gib |"
  echo "| Swap total GiB | $swap_total_gib |"
  echo
  echo "## Runtime Candidates"
  echo
  echo "| Runtime | Value |"
  echo "| --- | --- |"
  echo "| python3 | $python3_available |"
  echo "| node | $node_available |"
  echo "| llama-cli | $llama_cli_available |"
  echo "| llama-server | $llama_server_available |"
  echo "| llama.cpp command | $llama_cpp_available |"
  echo "| llama_cpp Python module | $llama_cpp_python_available |"
  echo "| ollama | $ollama_available |"
  echo "| vllm | $vllm_available |"
  echo "| torch | $torch_available |"
  echo "| transformers | $transformers_available |"
  echo "| accelerate | $accelerate_available |"
  echo "| sentencepiece | $sentencepiece_available |"
  echo "| Runtime summary | $runtime_summary |"
  echo
  echo "## Model Files"
  echo
  echo "| Check | Value |"
  echo "| --- | --- |"
  echo "| Candidate model-like files | $model_file_count |"
  echo "| Dream-named files | $dream_named_count |"
  echo
  echo "### Directories Checked"
  echo
  echo '```text'
  printf '%s' "$model_dir_lines"
  echo '```'
  echo
  echo "### Candidate Files"
  echo
  echo '```text'
  if [[ -n "$model_file_lines" ]]; then
    printf '%s' "$model_file_lines"
  else
    echo "none"
  fi
  echo '```'
  echo
  echo "## Baseline Meaning"
  echo
  echo "- This is a readiness report, not a model install or inference run."
  echo "- It does not download model files, call external APIs, or start a model server."
  if [[ "$verdict" == "candidate_runtime_and_model_present" ]]; then
    echo "- A bounded local inference smoke test is the next step before claiming Dream 7B deployment."
  elif [[ "$verdict" == "blocked_no_runtime" ]]; then
    echo "- Model-like files exist, but no supported local runtime was found."
  elif [[ "$verdict" == "blocked_no_model" ]]; then
    echo "- A local runtime exists, but no Dream 7B/model-like files were found in approved model directories."
  else
    echo "- Neither a Dream 7B/model-like file nor a supported local runtime was found in the approved checks."
  fi
} > "$report"

echo "$report"
