#!/usr/bin/env bash
set -euo pipefail

# Build experimental SM-T575 audio modules only.
# No kernel image, flashing, device access, or DTS activation.

if [[ $# -ne 2 ]]; then
    echo "Usage: $0 /path/to/patched/kernel /absolute/output"
    exit 2
fi

kernel="$(cd "$1" && pwd)"
output="$2"

[[ "$output" = /* ]] || {
    echo "Output must be an absolute path"
    exit 2
}

[[ -f "$kernel/Makefile" ]] || exit 1
[[ -f "$kernel/sound/soc/codecs/tas2562.c" ]] || exit 1
[[ -f "$kernel/sound/soc/codecs/tas2562.h" ]] || exit 1

case "$output" in
    /|/tmp|/var|/home|/mnt|"$kernel"|"$kernel"/*)
        echo "Unsafe output path"
        exit 2
        ;;
esac

root="$(cd "$(dirname "$0")/.." && pwd)"
cfg="$root/pmos/aports/device/testing/linux-postmarketos-exynos9810/config-postmarketos-exynos9810.aarch64"

mkdir -p "$output"
output="$(cd "$output" && pwd)"

build="$output/build"
external="$output/external"
mkdir -p "$build" "$external"

cp "$cfg" "$build/.config"

"$kernel/scripts/config" --file "$build/.config" \
    -m SND_SOC_TAS2562 \
    -m SND_SOC_SAMSUNG_GTACTIVE3LTE_TAS2562

echo "=== PREPARE KERNEL MODULE ENVIRONMENT ==="

make -C "$kernel" O="$build" \
    ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- LOCALVERSION= \
    olddefconfig modules_prepare

echo "=== VERIFY PRODUCTION KERNEL RELEASE ==="
release="$(make -s -C "$kernel" O="$build" \
    ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- LOCALVERSION= \
    kernelrelease)"

echo "Kernel release: $release"

if [[ "$release" != "7.3.0" ]]; then
    echo "FAIL: expected 7.3.0; refusing mismatched modules" >&2
    exit 1
fi

echo "=== BUILD KERNEL SYMBOL TABLE ==="

make -C "$kernel" O="$build" \
    ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- LOCALVERSION= \
    -j2 Image modules

test -s "$build/Module.symvers" || {
    echo "FAIL: kernel Module.symvers missing" >&2
    exit 1
}

echo "PASS: complete kernel build generated Module.symvers"

grep -qx 'CONFIG_SND_SOC_TAS2562=m' "$build/.config"
grep -qx 'CONFIG_SND_SOC_SAMSUNG_GTACTIVE3LTE_TAS2562=m' "$build/.config"

echo "=== PREPARE ONLY TWO AUDIO DRIVERS ==="

cp "$kernel/sound/soc/codecs/tas2562.c" "$external/"
cp "$kernel/sound/soc/codecs/tas2562.h" "$external/"
cp "$kernel/sound/soc/codecs/rt5665.h" "$external/"

# Adapt the include only in the disposable compilation copy.
sed 's|#include "../codecs/rt5665.h"|#include "rt5665.h"|' \
  "$root/drv/audio/t575/gtactive3lte_unified_candidate.c" \
  > "$external/gtactive3lte_unified_candidate.c"

grep -qx '#include "rt5665.h"' \
  "$external/gtactive3lte_unified_candidate.c"

cat > "$external/Makefile" <<'EOF'
obj-m += snd-soc-tas2562.o
snd-soc-tas2562-y := tas2562.o

obj-m += snd-soc-gtactive3lte-unified.o
snd-soc-gtactive3lte-unified-y := gtactive3lte_unified_candidate.o
EOF

echo "=== BUILD EXPERIMENTAL AUDIO MODULES ==="

# Allow inspection of unresolved symbols when the production
# Module.symvers is unavailable. This does NOT certify loadability.
make -C "$kernel" O="$build" \
    ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- LOCALVERSION= \
    M="$external" \
    -j2 modules

echo "=== RESULT ==="

find "$external" -maxdepth 1 -name '*.ko' -exec file {} \;

echo
echo "EXPERIMENTAL BUILD ONLY"
echo "Module symbols and running-kernel compatibility NOT verified."
echo "Do not install or load these modules."
echo "No kernel image built. No tablet modifications."
