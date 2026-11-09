#!/usr/bin/env bash
# Compile-only, zero-device-access SM-T575 standalone initramfs.
# NOT an Android BOOT image and not authorized for flashing.
set -euo pipefail
if [[ $# -ne 2 ]]; then
  echo "usage: bash scripts/t575-stage47-build-initramfs.sh PATCHED_KERNEL_DIR OUT_DIR" >&2
  exit 2
fi
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
kernel="$(cd "$1" && pwd)"
mkdir -p "$2"
out="$(cd "$2" && pwd)"
for cmd in aarch64-linux-gnu-gcc gzip file make; do
  command -v "$cmd" >/dev/null || { echo "missing tool: $cmd" >&2; exit 2; }
done
aarch64-linux-gnu-gcc -static -Os -Wall -Wextra \
  "$root/initramfs/t575-minimal-init.c" -o "$out/init"
file "$out/init"
# Build kernel host tool; no target kernel or device writes are performed.
make -C "$kernel" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- usr/gen_init_cpio
test -x "$kernel/usr/gen_init_cpio"
cat > "$out/initramfs.list" <<EOF
dir /dev 0755 0 0
nod /dev/console 0600 0 0 c 5 1
file /init $out/init 0755 0 0
EOF
"$kernel/usr/gen_init_cpio" "$out/initramfs.list" | gzip -n -9 > "$out/t575-diagnostic-initramfs.cpio.gz"
test -s "$out/t575-diagnostic-initramfs.cpio.gz"
echo "Diagnostic initramfs built offline. It is not a boot image and has NOT been run on hardware."
echo "RESTORE/BOOT/FLASH GATE: BLOCKED"
