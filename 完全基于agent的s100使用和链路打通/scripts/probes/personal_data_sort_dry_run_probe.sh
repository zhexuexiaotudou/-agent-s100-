#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export PERSONAL_DATA_SORT_DRY_RUN=1
exec bash "$script_dir/personal_data_sort_probe.sh" "$@"
