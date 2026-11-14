#!/bin/sh
# Passive package preflight: no compositor launch and no hardware writes.
set -eu

echo '=== Plasma Mobile aarch64 package preflight ==='
test "$(uname -m)" = aarch64
apk info -e plasma-mobile plasma-mobile-meta
echo '=== KWin / Plasma packages ==='
apk info -e kwin plasma-workspace
echo '=== Session files ==='
find /usr/share/wayland-sessions -maxdepth 2 -type f -print 2>/dev/null || true
echo '=== Executable candidates ==='
for exe in kwin_wayland startplasma-wayland; do
    command -v "$exe" || echo "Not found on PATH: $exe (inspect package)"
done
echo '=== DRM backends ==='
find /usr/lib -name '*_dri.so' -print 2>/dev/null | head -20 || true
echo '=== Package-only test complete; no GUI launched ==='
