#!/usr/bin/env bash
set -euo pipefail

package_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

python_cmd=()
for candidate in "py -3" python3 python; do
  read -r -a parts <<< "$candidate"
  if command -v "${parts[0]}" >/dev/null 2>&1 && "${parts[@]}" -c "import sys" >/dev/null 2>&1; then
    python_cmd=("${parts[@]}")
    break
  fi
done

if [[ ${#python_cmd[@]} -eq 0 ]]; then
  echo "no working python interpreter found" >&2
  exit 2
fi

"${python_cmd[@]}" "$package_root/SELF_CHECK.py"
