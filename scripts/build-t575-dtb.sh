#!/usr/bin/env bash
# Compile-only SM-T575 DTB, never flashes or makes a BOOT image.
set -euo pipefail
if [[ ${1:-} == "--help" || $# -ne 1 ]]; then
  echo "Usage: bash scripts/build-t575-dtb.sh /absolute/path/to/patched/linux" >&2
  exit 2
fi
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
kernel="$(cd "$1" && pwd)"
source_dts="$repo/dts/exynos9810-gtactive3lte.dts"
dtsdir="$kernel/arch/arm64/boot/dts/exynos"
upstream="$dtsdir/exynos9810-gtactive3wifi.dts"
target="$dtsdir/exynos9810-gtactive3lte.dts"
mk="$dtsdir/Makefile"
[[ -f "$upstream" && -f "$mk" ]] || {
  echo "Missing patched T570 kernel DTS / Makefile: $dtsdir" >&2
  exit 1
}
for token in 'pcie_0:' 'serial_1:' 'hsi2c_18:' 'rt5510:'; do
  if ! grep -Fq "$token" "$upstream"; then
    echo "Cannot find upstream label $token; update the LTE overlay first." >&2
    exit 1
  fi
done
if [[ -e "$target" ]] && ! cmp -s "$source_dts" "$target"; then
  echo "Refusing to replace existing LTE DTS with different content: $target" >&2
  exit 1
fi
cp "$source_dts" "$target"
if ! grep -Fq 'exynos9810-gtactive3lte.dtb' "$mk"; then
  printf '\ndtb-$(CONFIG_ARCH_EXYNOS) += exynos9810-gtactive3lte.dtb\n' >> "$mk"
fi
echo "Compiling SM-T575 DTB only (no kernel image, no flash)..."
make -C "$kernel" ARCH=arm64 exynos/exynos9810-gtactive3lte.dtb
echo "DTB compile completed; hardware validation and reversible boot procedure still REQUIRED."
