#!/usr/bin/env bash
# Stage 44: compile ONLY TAS2562 ARM64 codec object in an isolated output dir.
# No boot image, no module loading, no device, no source-tree mutations.
set -euo pipefail
if [[ $# -ne 2 || "${1:-}" == "--help" ]]; then
  echo "Usage: bash scripts/t575-stage44-compile-tas2562.sh /path/to/patched/kernel /path/to/isolated/output" >&2
  exit 2
fi
kernel="$(cd "$1" && pwd)"
output="$2"
if [[ "$output" != /* ]]; then
  echo "Output path must be absolute" >&2
  exit 2
fi
if [[ "$output" == "$kernel" || "$output" == "$kernel/"* || "$kernel" == "$output/"* ]]; then
  echo "Output must be separate from kernel source" >&2
  exit 2
fi
if [[ ! -f "$kernel/sound/soc/codecs/tas2562.c" || ! -f "$kernel/Makefile" ]]; then
  echo "Pinned kernel checkout/codec source missing" >&2
  exit 1
fi
command -v aarch64-linux-gnu-gcc >/dev/null || {
  echo "Missing aarch64-linux-gnu-gcc ARM64 cross compiler" >&2; exit 2;
}
mkdir -p "$output"
output="$(cd "$output" && pwd)"
case "$output" in
  /|/tmp|/var|/home|/mnt) echo "Unsafe output directory" >&2; exit 2 ;;
esac
echo "Stage 44: ARM64 TAS2562 codec object compile-only"
make -C "$kernel" O="$output" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- defconfig
"$kernel/scripts/config" --file "$output/.config" \
    -e I2C -e SOUND -e SND -e SND_SOC -m SND_SOC_TAS2562 \
    -m SND_SOC_SAMSUNG -m SND_SOC_SAMSUNG_EXYNOS9810_ABOX \
    -m SND_SOC_SAMSUNG_GTACTIVE3LTE_TAS2562
make -C "$kernel" O="$output" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- olddefconfig
grep -qx 'CONFIG_SND_SOC_TAS2562=m' "$output/.config" || {
  echo "TAS2562 option was not retained by Kconfig"; exit 1;
}
grep -qx 'CONFIG_SND_SOC_SAMSUNG_GTACTIVE3LTE_TAS2562=m' "$output/.config" || {
  echo "T575 experimental machine-driver option was not retained by Kconfig"; exit 1;
}
make -C "$kernel" O="$output" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- -j2 sound/soc/codecs/tas2562.o
make -C "$kernel" O="$output" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- -j2 sound/soc/samsung/gtactive3lte_tas2562.o
object="$output/sound/soc/codecs/tas2562.o"
test -s "$object"
test -s "$output/sound/soc/samsung/gtactive3lte_tas2562.o"
file "$object"
file "$output/sound/soc/samsung/gtactive3lte_tas2562.o"
file "$output/sound/soc/samsung/gtactive3lte_tas2562.o" | grep -Eq 'ARM aarch64|ARM64|AArch64'
file "$object" | grep -Eq 'ARM aarch64|ARM64|AArch64'
echo "PASS: TAS2562 codec and T575 ASoC machine AArch64 objects compiled; no boot image"
echo "No hardware accessed. RESTORE/BOOT/FLASH GATE: BLOCKED"
