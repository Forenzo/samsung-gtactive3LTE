#!/bin/sh
set -eu

PATH=/usr/sbin:/usr/bin:/sbin:/bin

DIR=/etc/t575-headphones
P=/sys/bus/platform/drivers/gtactive3lte-transport64
I=/sys/bus/i2c/drivers/rt5665
S=/sys/module/t575_tas2562_safeactive/parameters/allow_activation
FLAG=/run/t575-rt5665-test.active

exec >> "$DIR/rollback-v2.log" 2>&1
echo "=== RT5665 ROLLBACK ==="
date

exec 9>/run/t575-rt5665-switch.lock
flock -w 30 9 || {
    echo "FAIL: could not acquire switch lock"
    exit 1
}

# Do nothing unless an experiment is actually active.
if [ ! -f "$FLAG" ]; then
    echo "No active experiment; no action needed"
    exit 0
fi

restart_audio() {
    echo "=== RESTORE AUDIO SOCKETS ==="
    sudo -u __AUDIO_LOGIN__ env XDG_RUNTIME_DIR=/run/user/__AUDIO_UID__ DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/__AUDIO_UID__/bus systemctl --user start pipewire.socket pipewire-pulse.socket

    echo "=== RESTORE AUDIO SERVICES ==="
    sudo -u __AUDIO_LOGIN__ env XDG_RUNTIME_DIR=/run/user/__AUDIO_UID__ DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/__AUDIO_UID__/bus systemctl --user start pipewire.service pipewire-pulse.service wireplumber.service
}
# Best-effort restoration on an unexpected error.
cleanup() {
    result=$?
    trap - EXIT

    if ! grep -q '^snd_soc_rt5665 ' /proc/modules; then
        echo "WARNING: RT5665 absent; attempting original reload"
        modprobe snd_soc_rt5665 ||
            echo "ERROR: original RT5665 reload failed"
    fi

    if grep -q '^snd_soc_rt5665 ' /proc/modules; then
        if [ ! -L "$I/3-001b" ]; then
            printf '3-001b\n' > "$I/bind" || true
        fi
        if [ ! -L "$P/sound" ]; then
            printf 'sound\n' > "$P/bind" || true
        fi
    fi

    restart_audio || echo "WARNING: audio service restart failed"

    if [ "$result" -ne 0 ]; then
        echo "ROLLBACK FAILED: manual recovery may be required"
    fi
    exit "$result"
}

test "$(cat "$S")" = N || {
    echo "BLOCKED: speaker lock is not N"
    exit 1
}

trap cleanup EXIT

echo "=== DETACH UNIFIED CARD ==="
if [ -L "$P/sound" ]; then
    printf 'sound\n' > "$P/unbind"
fi

echo "=== DETACH RT5665 DEVICE ==="
if [ -L "$I/3-001b" ]; then
    printf '3-001b\n' > "$I/unbind"
fi

echo "=== REMOVE TEST CODEC ==="
if grep -q '^snd_soc_rt5665 ' /proc/modules; then
    timeout 20s rmmod snd_soc_rt5665
fi

echo "=== LOAD ORIGINAL CODEC ==="
modprobe snd_soc_rt5665

echo "=== RESTORE DEVICE BINDINGS ==="
if [ ! -L "$I/3-001b" ]; then
    printf '3-001b\n' > "$I/bind"
fi

if [ ! -L "$P/sound" ]; then
    printf 'sound\n' > "$P/bind"
fi

echo "=== VERIFY RECOVERY ==="
test -L "$I/3-001b"
test -L "$P/sound"
test "$(cat "$S")" = N
grep -q 'Active3' /proc/asound/cards

echo "PASS: original codec and ALSA card restored"
rm -f "$FLAG"
echo "ROLLBACK SUCCESSFUL"
