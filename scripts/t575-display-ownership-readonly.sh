#!/usr/bin/env bash
# Stage 12: read-only SM-T575 Android display/boot ownership inventory.
# No reboot, /dev/mem, MMIO access, partition reads or writes.
set -euo pipefail
umask 077
command -v adb >/dev/null || { echo "adb is required" >&2; exit 2; }
devices="$(adb devices | awk 'NR>1 && $2=="device" {print $1}')"
[[ "$(printf '%s\n' "$devices" | sed '/^$/d' | wc -l | tr -d ' ')" == "1" ]] || {
  echo "Exactly one authorized ADB device required." >&2; exit 2;
}
model="$(adb shell getprop ro.product.model | tr -d '\r')"
[[ "$model" == "SM-T575" ]] || { echo "Refusing unexpected model: $model" >&2; exit 1; }
out="${1:-./t575-stage12-readonly-$(date -u +%Y%m%dT%H%M%SZ)}"
[[ ! -e "$out" ]] || { echo "Output directory exists: $out" >&2; exit 1; }
mkdir -m 700 "$out"
capture() {
  local filename="$1"; shift
  if ! adb shell "$@" > "$out/$filename" 2>&1; then
    echo "(probe unavailable / denied; no workaround attempted)" >> "$out/$filename"
  fi
}
# Properties and files can be sensitive; keep all reports private.
capture 01-boot-cmdline.txt 'cat /proc/cmdline'
capture 02-iomem.txt 'cat /proc/iomem'
capture 03-framebuffer.txt 'for f in /sys/class/graphics/fb*/name /sys/class/graphics/fb*/virtual_size /sys/class/graphics/fb*/stride /sys/class/graphics/fb*/bits_per_pixel; do if [ -r "$f" ]; then echo "$f"; cat "$f"; fi; done'
capture 04-drm.txt 'for f in /sys/class/drm/card*/device/uevent /sys/class/drm/card*/dev; do if [ -r "$f" ]; then echo "$f"; cat "$f"; fi; done'
capture 05-display-drivers.txt 'ls -l /sys/bus/platform/drivers 2>/dev/null | grep -Ei "decon|dpu|drm|framebuffer|panel" || true'
capture 06-memory-map.txt 'cat /proc/meminfo; cat /proc/iomem | grep -Ei "framebuffer|decon|display|reserved" || true'
capture 07-device-model.txt 'getprop ro.product.model; getprop ro.boot.bootloader; getprop ro.boot.dtbo_idx; uname -r'
cat > "$out/README.txt" <<'END'
Stage 12: read-only SM-T575 display ownership inventory (Android).
Contains potentially identifying boot properties and memory layout.
NEVER publish the raw folder or serials to public GitHub.
Data describes the RUNNING ANDROID kernel, not necessarily S-Boot state
or mainline Linux driver ownership. Absence in sysfs is not proof of absence.
No /dev/mem, raw MMIO, registers, raw partition reads, flashing or reboot.
Keep the bootloader framebuffer reservation and DECON takeover disabled
until an independently tested recovery method is confirmed.
END
echo "Private read-only Stage 12 report: $out"
