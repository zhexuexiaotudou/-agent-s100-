#!/usr/bin/env bash
set -euo pipefail

# Final release cleanup requires a true 24-hour observation by default.
: "${AI_NAS_OBSERVATION_DURATION_SECONDS:=86400}"
: "${AI_NAS_OBSERVATION_INTERVAL_SECONDS:=300}"
export AI_NAS_OBSERVATION_DURATION_SECONDS
export AI_NAS_OBSERVATION_INTERVAL_SECONDS

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

case "$(uname -s 2>/dev/null || true)" in
  MINGW*|MSYS*|CYGWIN*)
    if command -v py >/dev/null 2>&1 && [[ -f "$ROOT_DIR/tools/production_delivery_gate.py" ]]; then
      exec py -3 "$ROOT_DIR/tools/production_delivery_gate.py" soak \
        --duration-seconds "$AI_NAS_OBSERVATION_DURATION_SECONDS" \
        --interval-seconds "$AI_NAS_OBSERVATION_INTERVAL_SECONDS"
    fi
    ;;
esac

exec "$SCRIPT_DIR/start_1h_observation.sh" "$@"
