#!/usr/bin/env bash
set -euo pipefail

repo_dir="${DREAM7B_DEFAULT_OPS_REPO_DIR:-$(pwd)}"
health_dir="${DREAM7B_DEFAULT_OPS_HEALTH_DIR:-/mnt/nas/openclaw/reports/models/dream7b_default_health}"

if [[ "$(id -u)" != "0" ]]; then
  echo "This installer must run as root." >&2
  exit 4
fi
if [[ ! -f "$repo_dir/scripts/dream7b-default-status" ]]; then
  echo "Missing status command in repo: $repo_dir/scripts/dream7b-default-status" >&2
  exit 2
fi
if [[ ! -f "$repo_dir/scripts/dream7b-default-rollback" ]]; then
  echo "Missing rollback command in repo: $repo_dir/scripts/dream7b-default-rollback" >&2
  exit 2
fi

install -m 0755 "$repo_dir/scripts/dream7b-default-status" /usr/local/bin/dream7b-default-status
install -m 0755 "$repo_dir/scripts/dream7b-default-rollback" /usr/local/bin/dream7b-default-rollback
mkdir -p "$health_dir"

cat > /etc/systemd/system/dream7b-default-health.service <<EOF
[Unit]
Description=Dream 7B default service health snapshot
After=dream7b-bpu-batch-queue.service

[Service]
Type=oneshot
ExecStart=/bin/bash -lc 'mkdir -p "$health_dir"; /usr/local/bin/dream7b-default-status --json > "$health_dir/latest_status.json.tmp" && mv "$health_dir/latest_status.json.tmp" "$health_dir/latest_status.json"; date -Is >> "$health_dir/health.log"'
EOF

cat > /etc/systemd/system/dream7b-default-health.timer <<'EOF'
[Unit]
Description=Run Dream 7B default health snapshot periodically

[Timer]
OnBootSec=2min
OnUnitActiveSec=5min
Persistent=true

[Install]
WantedBy=timers.target
EOF

cat > /etc/logrotate.d/dream7b-default-health <<EOF
$health_dir/*.log {
  rotate 14
  daily
  missingok
  notifempty
  compress
  copytruncate
}
EOF

systemctl daemon-reload
systemctl enable --now dream7b-default-health.timer >/dev/null
systemctl start dream7b-default-health.service

echo "installed_status_command=/usr/local/bin/dream7b-default-status"
echo "installed_rollback_command=/usr/local/bin/dream7b-default-rollback"
echo "installed_health_timer=dream7b-default-health.timer"
echo "health_dir=$health_dir"
