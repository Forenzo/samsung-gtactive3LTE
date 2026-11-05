#!/usr/bin/env bash
# SM-T575 read-only boot-chain preflight for macOS/Linux.
# Does not reboot, write partitions, flash, unlock, format, or change Android.
set -euo pipefail
umask 077
command -v adb >/dev/null || { echo "adb not found (install Android platform-tools)." >&2; exit 2; }
[[ "$(adb get-state 2>/dev/null)" == "device" ]] || {
  echo "Connect one authorized Android device over ADB first." >&2; exit 2;
}
serials="$(adb devices | awk 'NR>1 && $2=="device" {print $1}')"
[[ "$(printf '%s\n' "$serials" | sed '/^$/d' | wc -l | tr -d ' ')" == "1" ]] || {
  echo "Require exactly one authorized ADB device." >&2; exit 2;
}
model="$(adb shell getprop ro.product.model | tr -d '\r')"
[[ "$model" == "SM-T575" ]] || {
  echo "Refusing to probe unexpected device model: $model" >&2; exit 1;
}
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
out="${1:-./t575-boot-preflight-${stamp}}"
[[ ! -e "$out" ]] || { echo "Output path already exists: $out" >&2; exit 1; }
mkdir -m 700 "$out"
capture() {
  local file="$1"; shift
  # Errors are preserved in the local report instead of hiding probes.
  if ! adb shell "$@" > "$out/$file" 2>&1; then
    printf '\n(probe command failed; see output)\n' >> "$out/$file"
  fi
}
capture 01-identity.txt sh -c 'getprop ro.product.model; getprop ro.product.device; getprop ro.boot.bootloader; getprop ro.build.fingerprint; getprop ro.boot.flash.locked; getprop ro.boot.vbmeta.device_state; getprop ro.boot.verifiedbootstate'
capture 02-cmdline.txt cat /proc/cmdline
capture 03-storage.txt sh -c 'cat /proc/partitions; ls -l /dev/block/by-name /dev/block/platform/*/by-name 2>/dev/null || true'
capture 04-kernel.txt sh -c 'uname -a; cat /proc/version'
capture 05-mounts.txt sh -c 'cat /proc/mounts'
capture 06-dt-model.txt sh -c 'cat /proc/device-tree/model 2>/dev/null || cat /sys/firmware/devicetree/base/model 2>/dev/null || true'
capture 07-android-boot.txt sh -c 'getprop ro.boot.dtbo_idx; getprop ro.boot.hardware; getprop ro.boot.slot_suffix; getprop ro.boot.verifiedbootstate; getprop ro.boot.vbmeta.digest'
capture 08-root-availability.txt sh -c 'command -v su || true; id'
cat > "$out/README.txt" <<'END'
READ-ONLY SM-T575 boot preflight report
No partitions were read as raw images or modified.
Contains potentially identifying Android properties, boot cmdline and paths.
Keep this folder local/private. Do not commit it to public GitHub.
This is NOT a diagnostic boot image and does not authorize flashing.
Next: manually compare kernel cmdline, by-name targets and boot lock state
against the stock firmware package BEFORE any partition dump or boot test.
END
echo "Read-only report written to: $out"
echo "Keep it private; some fields can identify the tablet."
