#!/bin/sh
# SM-T575 LTE read-only inspection (macOS or Linux; adb required).
# No root, no flashing, no installation, no network access, no device writes.
# Collects selected non-identity facts only. REVIEW output before sharing.
set -eu
OUT=${1:-"t575-inventory"}
if ! command -v adb >/dev/null 2>&1; then
  echo "adb not found (install Android platform-tools)." >&2
  exit 1
fi
if [ -e "$OUT" ]; then
  echo "Output path exists. Choose a fresh private directory: $OUT" >&2
  exit 1
fi
if [ "$(adb get-state 2>/dev/null || true)" != device ]; then
  echo "No authorized ADB device. Enable USB debugging and approve this Mac." >&2
  exit 1
fi
MODEL=$(adb shell getprop ro.product.model | tr -d '\r')
if [ "$MODEL" != SM-T575 ]; then
  echo "Refusing snapshot: expected SM-T575, got $MODEL" >&2
  exit 1
fi
mkdir -m 700 "$OUT"
umask 077
{
  echo "# SM-T575 read-only inventory"
  echo "Collected (UTC): $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  echo
  echo "## Selected Android properties"
  for p in \
    ro.product.model ro.product.device ro.product.board \
    ro.hardware ro.board.platform ro.soc.model \
    ro.build.PDA ro.bootloader ro.build.version.release \
    ro.build.version.security_patch ro.boot.flash.locked \
    ro.boot.vbmeta.device_state ro.boot.verifiedbootstate \
    ro.boot.warranty_bit ro.boot.bootreason; do
      v=$(adb shell getprop "$p" | tr -d '\r')
      printf '%s=%s\n' "$p" "$v"
  done
  echo
  echo "## Kernel"
  adb shell uname -a | tr -d '\r'
  echo
  echo "## Partition names only (NO raw blocks)"
  adb shell 'ls -1 /dev/block/by-name 2>/dev/null || ls -1 /dev/block/bootdevice/by-name 2>/dev/null' | tr -d '\r'
  echo
  echo "## Block devices"
  adb shell 'cat /proc/partitions' | tr -d '\r'
  echo
  echo "## Input device driver names (avoid unique strings)"
  adb shell 'cat /proc/bus/input/devices' | tr -d '\r' | grep -E '^(N: Name=|H: Handlers=|P: Phys=)' | sed '/^P: Phys=/d' || true
  echo
  echo "## Device bus driver names"
  adb shell 'for d in /sys/bus/i2c/devices/* /sys/bus/spi/devices/*; do [ -d "$d" ] || continue; n=${d##*/}; [ -f "$d/name" ] && echo "$n: $(cat "$d/name")"; [ -f "$d/modalias" ] && echo "$n alias: $(cat "$d/modalias")"; done' | tr -d '\r'
} > "$OUT/inventory.txt"
cat >"$OUT/README.txt" <<'EOF'
LOCAL-ONLY DEVICE INVENTORY — REVIEW BEFORE SHARING.
Do not commit output to any public GitHub repository without inspection.
No EFS, serial, IMEI, MAC, credentials, firmware, userdata or raw image was
intentionally collected. Some Android properties or device names can still
reveal unexpected personal or device-specific information.
The tool does not change the device and does not require root.
For live DTB and hardware-register comparisons, a separate reviewed rooted
snapshot may be necessary; preserve it OFF GitHub.
EOF
echo "Created $OUT/inventory.txt — local-only. Review carefully before sharing."
