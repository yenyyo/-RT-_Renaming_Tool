#!/usr/bin/env bash
set -euo pipefail

safe_lazy_unmount() {
  local mp="$1"

  # 1) initiate lazy unmount
  umount -l "$mp"
  if [ $? -ne 0 ]; then
    echo "[!] Failed to start lazy unmount on $mp"
    return 1
  fi
  echo "[…] Lazy unmount initiated for $mp"

  # 2) poll until the mountpoint disappears
  while mountpoint -q "$mp"; do
    sleep 1
  done

  # 3) now it’s really gone
  echo "[✔] Fully unmounted $mp"
  return 0
}

# ─────────────────────────────────────────────
# Script entrypoint
# ─────────────────────────────────────────────
if [ $# -ne 1 ]; then
  echo "Usage: $0 <mount-point>"
  exit 1
fi

MOUNT_POINT="$1"
safe_lazy_unmount "$MOUNT_POINT"