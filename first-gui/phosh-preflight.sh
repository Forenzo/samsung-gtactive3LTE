#!/bin/sh
# Build-only checks inside the aarch64 Alpine rootfs.
set -eu
for pkg in phosh phoc squeekboard labwc yambar fuzzel foot seatd eudev dbus; do
    apk info -e "$pkg" >/dev/null || { echo "Missing package: $pkg" >&2; exit 1; }
done
for executable in /usr/bin/phoc /usr/bin/labwc /usr/bin/seatd /usr/bin/squeekboard /usr/bin/yambar /usr/bin/fuzzel; do
    [ -x "$executable" ] || { echo "Missing executable: $executable" >&2; exit 1; }
done
if [ -x /usr/bin/phosh-session ]; then
    echo "Phosh entry: /usr/bin/phosh-session"
elif [ -x /usr/libexec/phosh ]; then
    echo "Phosh entry: /usr/libexec/phosh (direct shell)"
elif command -v phosh >/dev/null 2>&1; then
    echo "Phosh entry: $(command -v phosh)"
else
    echo 'Missing Phosh shell executable/session; inspect package layout' >&2
    exit 1
fi
[ ! -x /usr/bin/startplasma-wayland ] || { echo 'Unexpected Plasma/KWin dependency' >&2; exit 1; }
echo 'PASS: separate Phosh/Phoc touch session + optional labwc windowed session'
echo 'NO tablet hardware, GPU, touchscreen or full desktop boot was tested'
