#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/mount_openclaw_nas.sh --protocol smb --host <NAS_IP> --share OpenClawWorkspace [options]
  scripts/mount_openclaw_nas.sh --protocol nfs --host <NAS_IP> --share /share/OpenClawWorkspace [options]

Options:
  --mountpoint <path>          Default: /mnt/nas/openclaw
  --credentials-file <path>    SMB only. Default: /root/.smbcredentials-openclaw
  --username <name>            SMB only. Used with --create-credentials.
  --domain <name>              SMB only. Optional domain/workgroup for credentials file.
  --create-credentials         SMB only. Writes credentials from OPENCLAW_NAS_PASSWORD.
  --smb-vers <version>         SMB only. Default: 3.0
  --nfs-vers <version>         NFS only. Default: 4
  --write-fstab                Print, and with --apply append, the persistent mount line.
  --init-workspace             Run scripts/init_nas_workspace.sh after a successful mount.
  --apply                      Actually create credentials, mount, and optionally write fstab.

Default mode is dry-run. It validates inputs and prints the commands/lines it
would use, but it does not mount anything or write system files.
EOF
}

die() {
  echo "$*" >&2
  exit 2
}

shell_quote() {
  printf "'%s'" "$(printf "%s" "$1" | sed "s/'/'\\\\''/g")"
}

protocol=""
host=""
share=""
mountpoint="/mnt/nas/openclaw"
credentials_file="/root/.smbcredentials-openclaw"
username=""
domain=""
smb_vers="3.0"
nfs_vers="4"
create_credentials=0
write_fstab=0
init_workspace=0
apply=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --protocol) protocol="${2:-}"; shift 2 ;;
    --host) host="${2:-}"; shift 2 ;;
    --share) share="${2:-}"; shift 2 ;;
    --mountpoint) mountpoint="${2:-}"; shift 2 ;;
    --credentials-file) credentials_file="${2:-}"; shift 2 ;;
    --username) username="${2:-}"; shift 2 ;;
    --domain) domain="${2:-}"; shift 2 ;;
    --smb-vers) smb_vers="${2:-}"; shift 2 ;;
    --nfs-vers) nfs_vers="${2:-}"; shift 2 ;;
    --create-credentials) create_credentials=1; shift ;;
    --write-fstab) write_fstab=1; shift ;;
    --init-workspace) init_workspace=1; shift ;;
    --apply) apply=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "Unknown argument: $1" ;;
  esac
done

case "$protocol" in
  smb|nfs) ;;
  "") die "Missing --protocol" ;;
  *) die "Unsupported protocol: $protocol" ;;
esac

[[ -n "$host" ]] || die "Missing --host"
[[ -n "$share" ]] || die "Missing --share"

case "$mountpoint" in
  /mnt/nas/openclaw|/mnt/nas/openclaw/*) ;;
  *) die "Refusing mountpoint outside /mnt/nas/openclaw: $mountpoint" ;;
esac

if [[ "$protocol" == "smb" ]]; then
  [[ "$share" != /* ]] || die "SMB share should be a share name, not a path: $share"
  source_spec="//$host/$share"
  mount_type="cifs"
  mount_options="credentials=$credentials_file,vers=$smb_vers,iocharset=utf8,uid=0,gid=0,file_mode=0640,dir_mode=0750"
  dependency="mount.cifs"
else
  [[ "$share" == /* ]] || die "NFS share should be an export path, for example /share/OpenClawWorkspace"
  source_spec="$host:$share"
  mount_type="nfs"
  mount_options="vers=$nfs_vers"
  dependency="mount.nfs"
fi

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
init_script="$repo_dir/scripts/init_nas_workspace.sh"
fstab_line="$source_spec $mountpoint $mount_type $mount_options,nofail,x-systemd.automount 0 0"

echo "protocol=$protocol"
echo "host=$host"
echo "share=$share"
echo "mountpoint=$mountpoint"
echo "source=$source_spec"
echo "mode=$([[ "$apply" == 1 ]] && echo apply || echo dry-run)"
echo

echo "## checks"
if command -v "$dependency" >/dev/null 2>&1; then
  echo "$dependency=ok"
else
  echo "$dependency=missing"
fi

if ping -c 1 -W 2 "$host" >/dev/null 2>&1; then
  echo "ping=ok"
else
  echo "ping=failed"
fi

if findmnt "$mountpoint" >/dev/null 2>&1; then
  echo "already_mounted=yes"
else
  echo "already_mounted=no"
fi

echo
echo "## planned mount"
printf 'mkdir -p %s\n' "$(shell_quote "$mountpoint")"
printf 'mount -t %s %s %s -o %s\n' \
  "$mount_type" \
  "$(shell_quote "$source_spec")" \
  "$(shell_quote "$mountpoint")" \
  "$(shell_quote "$mount_options")"

if [[ "$write_fstab" == 1 ]]; then
  echo
  echo "## fstab line"
  echo "$fstab_line"
fi

if [[ "$apply" != 1 ]]; then
  echo
  echo "DRY_RUN_DONE"
  exit 0
fi

[[ "$(id -u)" == "0" ]] || die "--apply requires root"
command -v "$dependency" >/dev/null 2>&1 || die "Missing dependency: $dependency"

if [[ "$protocol" == "smb" && "$create_credentials" == 1 ]]; then
  [[ -n "$username" ]] || die "--create-credentials requires --username"
  [[ -n "${OPENCLAW_NAS_PASSWORD:-}" ]] || die "--create-credentials requires OPENCLAW_NAS_PASSWORD in the environment"
  umask 077
  {
    printf 'username=%s\n' "$username"
    printf 'password=%s\n' "$OPENCLAW_NAS_PASSWORD"
    [[ -z "$domain" ]] || printf 'domain=%s\n' "$domain"
  } > "$credentials_file"
  chmod 600 "$credentials_file"
  echo "credentials_file_written=$credentials_file"
fi

if [[ "$protocol" == "smb" && ! -f "$credentials_file" ]]; then
  die "Missing SMB credentials file: $credentials_file"
fi

mkdir -p "$mountpoint"

if findmnt "$mountpoint" >/dev/null 2>&1; then
  echo "mount_skipped=already_mounted"
else
  mount -t "$mount_type" "$source_spec" "$mountpoint" -o "$mount_options"
  echo "mount=ok"
fi

findmnt "$mountpoint"
mkdir -p "$mountpoint/tmp"
touch "$mountpoint/tmp/.write_test"
rm "$mountpoint/tmp/.write_test"
echo "write_test=ok"

if [[ "$init_workspace" == 1 ]]; then
  [[ -x "$init_script" || -f "$init_script" ]] || die "Missing init script: $init_script"
  bash "$init_script" "$mountpoint"
fi

if [[ "$write_fstab" == 1 ]]; then
  if grep -F " $mountpoint " /etc/fstab >/dev/null 2>&1; then
    echo "fstab_skipped=mountpoint_already_present"
  else
    cp /etc/fstab "/etc/fstab.bak-openclaw-$(date +%Y%m%d-%H%M%S)"
    printf '%s\n' "$fstab_line" >> /etc/fstab
    systemctl daemon-reload || true
    echo "fstab_appended=ok"
  fi
fi

echo "MOUNT_OPENCLAW_NAS_OK"
