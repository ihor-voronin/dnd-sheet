#!/usr/bin/env bash
# Server setup: Docker, firewall, swap, backups, key-only SSH sign-in.
# Idempotent: a repeated run breaks nothing, it only brings the server to the desired state.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

DISABLE_PASSWORD_LOGIN="${1:-true}"

# shellcheck source=/dev/null  # the file exists only on the server
. /etc/os-release
case "$ID" in
  ubuntu | debian) ;;
  *)
    echo "Unsupported OS: $ID (Ubuntu or Debian required)" >&2
    exit 1
    ;;
esac

apt-get update -q
apt-get install -yq ca-certificates curl gnupg ufw sqlite3 unattended-upgrades

# Docker from the official Docker repository (it has the compose v2 plugin).
if ! command -v docker >/dev/null 2>&1; then
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL "https://download.docker.com/linux/${ID}/gpg" -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/${ID} ${VERSION_CODENAME} stable" \
    >/etc/apt/sources.list.d/docker.list
  apt-get update -q
  apt-get install -yq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
systemctl enable --now docker

# 2 GB swap: PDF rendering (WeasyPrint) likes memory, and the VPS has 2.5 GB.
if ! swapon --show | grep -q '/swapfile'; then
  fallocate -l 2G /swapfile 2>/dev/null || dd if=/dev/zero of=/swapfile bs=1M count=2048
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
fi
grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' >>/etc/fstab

# Firewall: SSH and web only.
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

# App directories. The container runs as a user with uid 10001.
install -d -m 0755 /opt/dndsheet /opt/dndsheet/backups
install -d -m 0755 -o 10001 -g 10001 /opt/dndsheet/var

# A daily database backup, kept for 14 days.
cat >/etc/cron.daily/dndsheet-backup <<'CRON'
#!/bin/sh
set -e
DB=/opt/dndsheet/var/dndsheet.sqlite3
[ -f "$DB" ] || exit 0
sqlite3 "$DB" ".backup '/opt/dndsheet/backups/dndsheet-$(date +%F).sqlite3'"
find /opt/dndsheet/backups -name 'dndsheet-*.sqlite3' -mtime +14 -delete
CRON
chmod 0755 /etc/cron.daily/dndsheet-backup

# Key-only SSH sign-in. Terraform has just logged in with the key, so the key works.
if [ "$DISABLE_PASSWORD_LOGIN" = "true" ]; then
  install -d /etc/ssh/sshd_config.d
  cat >/etc/ssh/sshd_config.d/10-dndsheet.conf <<'SSHD'
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin prohibit-password
SSHD
  sshd -t
  systemctl reload ssh 2>/dev/null || systemctl reload sshd
fi

echo "bootstrap: done"
