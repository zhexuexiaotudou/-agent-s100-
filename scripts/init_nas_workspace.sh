#!/usr/bin/env bash
set -euo pipefail

workspace="${1:-/mnt/nas/openclaw}"

case "$workspace" in
  ""|"/"|"/mnt"|"/mnt/nas"|"/home"|"/root")
    echo "Refusing unsafe workspace path: $workspace" >&2
    exit 2
    ;;
esac

mkdir -p "$workspace"/{inbox,outbox,documents,photos,videos,robot_datasets,tmp}
mkdir -p "$workspace"/logs/{openclaw,probes,robot}
mkdir -p "$workspace"/reports/{daily,weekly,experiments}

cat > "$workspace/README.md" <<'EOF'
# OpenClawWorkspace

This directory is the only NAS workspace OpenClaw should use in the first baseline.

## Directories

- inbox: human-provided inputs for agent jobs
- outbox: generated outputs for review
- documents: source documents for indexing and summaries
- photos: source images
- videos: source videos
- robot_datasets: ROS bags, sensor captures, and dataset cards
- logs: append-only service, probe, and robot logs
- reports: daily, weekly, and experiment reports
- tmp: temporary files that may be cleaned

Do not store API keys, SSH keys, tokens, or NAS admin credentials here.
EOF

echo "Initialized OpenClaw NAS workspace at: $workspace"
find "$workspace" -maxdepth 2 -type d | sort
