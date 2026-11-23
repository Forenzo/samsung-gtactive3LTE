#!/bin/sh
# SM-T575 E8B lifecycle-only event test. NO AMPLIFIER ACTIVATION.
# Run as root after stopping PipeWire/WirePlumber. E4E restored on exit.
set -eu
OLD=/home/Xnopish/t575-audio-stage-e4e/t575-tas2562-safeactive.ko
NEW=/home/Xnopish/t575-audio-stage-e8b/t575-tas2562-safeactive.ko
TONE=/home/Xnopish/t575-audio-stage-e4f/quiet-440-s32le.raw
CARD=/sys/bus/platform/devices/sound
TRANSPORT=/sys/bus/platform/drivers/gtactive3lte-transport64
AMP=/sys/bus/i2c/devices/4-004c
CODEC=/sys/bus/i2c/drivers/t575-tas2562-safeactive
MOD=t575_tas2562_safeactive
PIN=/sys/kernel/debug/pinctrl/14220000.pinctrl-samsung-pinctrl/pins
EXPECTED_OLD=24154adb80bfebd56dd76cc18b269d1fcedf7a33f4ac3785a1c797458fd650ab
TOUCHED=0
PCM_PID=
pin_low() { grep '^pin 16 (gpm40-0)' "$PIN" | grep -F 'CON(0x1) DAT(0x0)'; }
loaded() { grep -q "^$MOD " /proc/modules; }
restoration() {
    rc=$?
    trap - EXIT HUP INT TERM
    set +e
    if [ -n "$PCM_PID" ]; then
        kill "$PCM_PID" 2>/dev/null
        wait "$PCM_PID" 2>/dev/null
    fi
    if [ "$TOUCHED" -eq 1 ]; then
        echo '=== RESTORE ACTIVATION-LOCKED E4E ==='
        [ ! -L "$CARD/driver" ] || printf sound > "$TRANSPORT/unbind"
        [ ! -L "$AMP/driver" ] || printf 4-004c > "$CODEC/unbind"
        loaded && rmmod "$MOD"
        if ! loaded; then insmod "$OLD" allow_activation=0; fi
        [ -L "$CARD/driver" ] || printf sound > "$TRANSPORT/bind"
    fi
    echo '=== FINAL HARDWARE CHECK ==='
    pin_low || rc=1
    [ -L "$AMP/driver" ] || rc=1
    [ -L "$CARD/driver" ] || rc=1
    [ "$(cat /sys/module/$MOD/parameters/allow_activation 2>/dev/null)" = N ] || rc=1
    if [ "$rc" -eq 0 ]; then
        echo 'PASS: E8B event test completed, E4E restored, amplifier OFF'
    else
        echo 'FAIL: inspect module bindings and SDZ before doing anything else' >&2
    fi
    exit "$rc"
}
trap restoration EXIT
trap 'exit 130' INT
trap 'exit 129' HUP
trap 'exit 143' TERM

echo '=== E8B STRICT PREFLIGHT ==='
[ "$(modinfo -F description "$NEW")" = 'SM-T575 E8B one-shot abort-latched activation candidate' ] || { echo 'FAIL: unexpected module description' >&2; exit 1; }
[ "$#" -eq 1 ]
NEW_SHA="$1"
[ "$(uname -r)" = 7.3.0 ]
[ -s "$OLD" ] && [ -s "$NEW" ] && [ -s "$TONE" ]
[ "$(sha256sum "$OLD" | cut -d ' ' -f 1)" = "$EXPECTED_OLD" ]
[ "$(sha256sum "$NEW" | cut -d ' ' -f 1)" = "$NEW_SHA" ]
[ "$(modinfo -F vermagic "$NEW" | cut -d ' ' -f 1)" = 7.3.0 ]
[ "$(cat /sys/module/$MOD/parameters/allow_activation)" = N ]
[ -L "$CARD/driver" ] && [ -L "$AMP/driver" ]
pin_low
for dev in /dev/snd/pcmC0D0p /dev/snd/pcmC0D1p /dev/snd/pcmC0D0c; do
    if [ -e "$dev" ] && fuser -s "$dev" 2>/dev/null; then
        echo "FAIL: PCM busy: $dev" >&2
        exit 1
    fi
done

echo '=== E8B LOCKED REPLACE (AMP ALWAYS OFF) ==='
TOUCHED=1
printf sound > "$TRANSPORT/unbind"
pin_low
printf 4-004c > "$CODEC/unbind"
pin_low
rmmod "$MOD"
pin_low
insmod "$NEW" allow_activation=0
pin_low
[ -L "$AMP/driver" ]
[ "$(cat /sys/module/$MOD/parameters/allow_activation)" = N ]
printf sound > "$TRANSPORT/bind"
[ -L "$CARD/driver" ]
pin_low

echo '=== E8B RUN 2-SECOND SILENT SPEAKER-PCM STREAM ==='
# Aplay generates ALSA activity while the codec's SDZ remains LOW.
aplay -q -D hw:0,1 -t raw -f S32_LE -r 48000 -c 2 "$TONE" \
  >/home/Xnopish/t575-audio-stage-e8b/aplay.log 2>&1 &
PCM_PID=$!
wait "$PCM_PID"
PCM_PID=
pin_low

echo '=== E8B DENIED-ACTIVATION CHECK ==='
echo '=== VERIFY ABORT ON PCM CLOSE ==='
dmesg | grep 'E8: PCM closed, amplifier OFF' | tail -5
# The E8B candidate is loaded with allow_activation=0 in this test.
# PCM start must NOT schedule activation work or change SDZ.
if dmesg | grep 'E8B: one-shot PCM-triggered validation BEGIN'; then
    echo 'FAIL: unexpected E8B activation request' >&2
    exit 1
fi
echo 'PASS: E8B activation work never scheduled'
echo '=== E8B TEST STREAM CLOSED ==='
grep -x closed /proc/asound/card0/pcm1p/sub0/status
