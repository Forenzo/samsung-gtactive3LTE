#!/usr/bin/env bash
# Stage 12: read-only framebuffer and boot-chain metadata from SM-T575.
# No MMIO probing, flashing, reboots, sysfs writes, partition dumps or module loading.
set -euo pipefail
umask 077
command -v adb >/dev/null || { echo "adb is required" >&2; exit 2; }
n="$(adb devices | awk 'NR>1 && $2=="device" {n++} END {print n+0}')"
[[ "$n" == 1 ]] || { echo "Require exactly one authorized ADB device" >&2; exit 2; }
model="$(adb shell getprop ro.product.model | tr -d '\r')"
[[ "$model" == "SM-T575" ]] || { echo "Refusing unexpected model: $model" >&2; exit 1; }
root="$(adb shell 'su -c id' 2>/dev/null | tr -d '\r' || true)"
[[ "$root" == *'uid=0('* ]] || { echo "Read-only probes require working su" >&2; exit 1; }
out="${1:-./t575-stage12-$(date -u +%Y%m%dT%H%M%SZ)}"
[[ ! -e "$out" ]] || { echo "Output already exists: $out" >&2; exit 1; }
mkdir -m 700 "$out"
probe() {
  local filename="$1"; shift
  if ! adb shell su -c "$*" > "$out/$filename" 2>&1; then
    printf '\n(probe unavailable on this kernel)\n' >> "$out/$filename"
  fi
}
probe 01-framebuffer.txt 'cat /proc/fb 2>&1; for x in /sys/class/graphics/fb*/name /sys/class/graphics/fb*/virtual_size /sys/class/graphics/fb*/stride /sys/class/graphics/fb*/bits_per_pixel /sys/class/graphics/fb*/modes; do if [ -f "$x" ]; then echo "=== $x"; cat "$x"; fi; done'
probe 02-memory-mapping.txt 'cat /proc/iomem; cat /proc/meminfo | head -n 10'
probe 03-display-logs.txt 'dmesg | grep -i -E "decon|display|dpu|dsim|framebuffer|simpledrm|simplefb|fb0|iommu|sysmmu" | tail -n 180'
probe 04-boot-metadata.txt 'cat /proc/cmdline; cat /proc/device-tree/model 2>/dev/null; echo; getprop ro.boot.bootloader; getprop ro.boot.dtbo_idx; getprop ro.boot.verifiedbootstate'
probe 05-dt-display.txt 'for x in /proc/device-tree/chosen/framebuffer-0 /sys/firmware/devicetree/base/chosen/framebuffer-0 /proc/device-tree/reserved-memory/bootloader_fb; do if [ -d "$x" ]; then echo "=== $x"; ls -l "$x"; fi; done'
cat > "$out/README.txt" <<'END'
SM-T575 Stage 12 read-only display/boot ownership evidence.
The output may contain device identifiers, addresses, kernel command-line
values and Android details. Keep it private; never commit it to GitHub.
This is kernel/user-space metadata, NOT direct DECON register verification.
Masked /proc/iomem output cannot prove a physical memory map.
No flash, reboot, partition dump, sysfs write or driver insertion occurred.
DO NOT flash a DTB based on this report.
END
echo "Private Stage 12 report: $out"
echo "Redact identifiers before sharing excerpts."
