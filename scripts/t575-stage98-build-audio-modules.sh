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

if [[ "${T575_USE_CCACHE:-0}" == "1" ]]; then
    command -v ccache >/dev/null
    export CC="ccache ${T575_CROSS_COMPILE-aarch64-linux-gnu-}gcc"
fi

build="$output/build"
external="$output/external"
mkdir -p "$build" "$external"

cp "$cfg" "$build/.config"

"$kernel/scripts/config" --file "$build/.config" \
    -m SND_SOC_TAS2562 \
    -m SND_SOC_SAMSUNG_GTACTIVE3LTE_TAS2562

echo "=== PREPARE KERNEL MODULE ENVIRONMENT ==="

make -C "$kernel" O="$build" \
    ARCH=arm64 \
    CROSS_COMPILE="${T575_CROSS_COMPILE-aarch64-linux-gnu-}" \
    LOCALVERSION= \
    KBUILD_BUILD_VERSION="${T575_BUILD_VERSION:-27-postmarketOS}" \
    olddefconfig modules_prepare

echo "=== VERIFY PRODUCTION KERNEL RELEASE ==="
release="$(make -s -C "$kernel" O="$build" \
    ARCH=arm64 \
    CROSS_COMPILE="${T575_CROSS_COMPILE-aarch64-linux-gnu-}" \
    LOCALVERSION= \
    KBUILD_BUILD_VERSION="${T575_BUILD_VERSION:-27-postmarketOS}" \
    kernelrelease)"

echo "Kernel release: $release"

if [[ "$release" != "7.3.0" ]]; then
    echo "FAIL: expected 7.3.0; refusing mismatched modules" >&2
    exit 1
fi

echo "=== REUSE VERIFIED KERNEL SYMBOL TABLE ==="

if [[ -n "${T575_KERNEL_SYMVERS:-}" ]]; then
    [[ -s "$T575_KERNEL_SYMVERS" ]] || {
        echo "FAIL: existing kernel symbol table missing" >&2
        exit 1
    }
    cp "$T575_KERNEL_SYMVERS" "$build/Module.symvers"
    echo "PASS: existing kernel Module.symvers reused; no Image/modules rebuild"
else
    echo "=== BUILD KERNEL SYMBOL TABLE (SLOW PATH) ==="
    make -C "$kernel" O="$build" \
        ARCH=arm64 \
        CROSS_COMPILE="${T575_CROSS_COMPILE-aarch64-linux-gnu-}" \
        LOCALVERSION= \
        KBUILD_BUILD_VERSION="${T575_BUILD_VERSION:-27-postmarketOS}" \
        -j2 Image modules
fi

test -s "$build/Module.symvers" || {
    echo "FAIL: kernel Module.symvers missing" >&2
    exit 1
}
echo "PASS: kernel symbol table available"

grep -qx 'CONFIG_SND_SOC_TAS2562=m' "$build/.config"
grep -qx 'CONFIG_SND_SOC_SAMSUNG_GTACTIVE3LTE_TAS2562=m' "$build/.config"

echo "=== PREPARE EXPERIMENTAL AUDIO DRIVERS ==="

cp "$kernel/sound/soc/codecs/tas2562.c" "$external/"
python3 "$root/scripts/t575-stage100-harden-tas2562.py" "$external/tas2562.c"
cp "$kernel/sound/soc/codecs/tas2562.h" "$external/"
cp "$root/drv/audio/t575/tas2562_detect.c" "$external/"
cp "$root/drv/audio/t575/tas2562_locked.c" "$external/"
cp "$root/drv/audio/t575/tas2562_safeinit.c" "$external/"
cp "$root/drv/audio/t575/tas2562_safeconfig.c" "$external/"
cp "$root/drv/audio/t575/tas2562_transport.c" "$external/"
cp "$root/drv/audio/t575/tas2562_transport64.c" "$external/"
cp "$root/drv/audio/t575/tas2562_clockcheck.c" "$external/"
cp "$root/drv/audio/t575/tas2562_protectcheck.c" "$external/"
cp "$root/drv/audio/t575/tas2562_safeactive.c" "$external/"
cp "$kernel/sound/soc/codecs/rt5665.h" "$external/"

# Adapt the include only in the disposable compilation copy.
sed 's|#include "../codecs/rt5665.h"|#include "rt5665.h"|' \
  "$root/drv/audio/t575/gtactive3lte_unified_candidate.c" \
  > "$external/gtactive3lte_unified_candidate.c"

grep -qx '#include "rt5665.h"' \
  "$external/gtactive3lte_unified_candidate.c"


sed 's|#include "../codecs/rt5665.h"|#include "rt5665.h"|' \
    "$root/drv/audio/t575/gtactive3lte_transport.c" \
    > "$external/gtactive3lte_transport.c"

sed 's|#include "../codecs/rt5665.h"|#include "rt5665.h"|' \
    "$root/drv/audio/t575/gtactive3lte_transport64.c" \
    > "$external/gtactive3lte_transport64.c"

grep -qx '#include "rt5665.h"' \
    "$external/gtactive3lte_transport64.c"


cat > "$external/Makefile" <<'EOF'
obj-m += t575-tas2562-safeinit.o
t575-tas2562-safeinit-y := tas2562_safeinit.o

obj-m += t575-tas2562-safeconfig.o
t575-tas2562-safeconfig-y := tas2562_safeconfig.o

obj-m += t575-tas2562-transport.o
t575-tas2562-transport-y := tas2562_transport.o

obj-m += snd-soc-gtactive3lte-transport.o
snd-soc-gtactive3lte-transport-y := gtactive3lte_transport.o

obj-m += t575-tas2562-transport64.o
t575-tas2562-transport64-y := tas2562_transport64.o

obj-m += t575-tas2562-clockcheck.o
t575-tas2562-clockcheck-y := tas2562_clockcheck.o

obj-m += t575-tas2562-protectcheck.o
t575-tas2562-protectcheck-y := tas2562_protectcheck.o

obj-m += t575-tas2562-safeactive.o
t575-tas2562-safeactive-y := tas2562_safeactive.o

obj-m += snd-soc-gtactive3lte-transport64.o
snd-soc-gtactive3lte-transport64-y := gtactive3lte_transport64.o



obj-m += t575-tas2562-locked.o
t575-tas2562-locked-y := tas2562_locked.o

obj-m += t575-tas2562-detect.o
t575-tas2562-detect-y := tas2562_detect.o

obj-m += snd-soc-tas2562.o
snd-soc-tas2562-y := tas2562.o

obj-m += snd-soc-gtactive3lte-unified.o
snd-soc-gtactive3lte-unified-y := gtactive3lte_unified_candidate.o
EOF

echo "=== BUILD EXPERIMENTAL AUDIO MODULES ==="

# Allow inspection of unresolved symbols when the production
# Module.symvers is unavailable. This does NOT certify loadability.
make -C "$kernel" O="$build" \
    ARCH=arm64 \
    CROSS_COMPILE="${T575_CROSS_COMPILE-aarch64-linux-gnu-}" \
    LOCALVERSION= \
    KBUILD_BUILD_VERSION="${T575_BUILD_VERSION:-27-postmarketOS}" \
    M="$external" \
    -j2 modules

echo "=== RESULT ==="

find "$external" -maxdepth 1 -name '*.ko' -exec file {} \;

echo
echo "EXPERIMENTAL BUILD ONLY"
echo "Module symbols and running-kernel compatibility NOT verified."
echo "Do not install or load these modules."
echo "No kernel image built. No tablet modifications."
