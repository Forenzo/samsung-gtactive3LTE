#!/bin/sh
# SM-T575 E9 one-shot PCM-triggered, very-low-level active speaker diagnostic.
# Run as root ONLY after stopping desktop audio, with matching kernel 7.3.0.
set -eu

OLD=/home/Xnopish/t575-audio-stage-e4e/t575-tas2562-safeactive.ko
NEW=/home/Xnopish/t575-audio-stage-e9/t575-tas2562-safeactive.ko
TONE=/home/Xnopish/t575-audio-stage-e4f/quiet-440-s32le.raw
CARD=/sys/bus/platform/devices/sound
TRANSPORT=/sys/bus/platform/drivers/gtactive3lte-transport64
AMP=/sys/bus/i2c/devices/4-004c
CODEC=/sys/bus/i2c/drivers/t575-tas2562-safeactive
MOD=t575_tas2562_safeactive
PIN=/sys/kernel/debug/pinctrl/14220000.pinctrl-samsung-pinctrl/pins

EXPECTED_NEW_SHA="$1"
TOUCHED=0
PCM_PID=

pin_low() {
    grep '^pin 16 (gpm40-0)' "$PIN" | grep -F 'CON(0x1) DAT(0x0)'
}
loaded() { grep -q "^$MOD " /proc/modules; }

restore() {
    rc=$?
    trap - EXIT HUP INT TERM
    set +e
    [ -z "$PCM_PID" ] || { kill "$PCM_PID" 2>/dev/null; wait "$PCM_PID" 2>/dev/null; }
    if [ "$TOUCHED" -eq 1 ]; then
        echo '=== RESTORING KNOWN-GOOD ACTIVATION-LOCKED E4E ==='
        [ ! -L "$CARD/driver" ] || printf 'sound' > "$TRANSPORT/unbind"
        [ ! -L "$AMP/driver" ] || printf '4-004c' > "$CODEC/unbind"
        loaded && rmmod "$MOD"
        if ! loaded; then insmod "$OLD" allow_activation=0; fi
        [ -L "$CARD/driver" ] || printf 'sound' > "$TRANSPORT/bind"
    fi
    echo '=== FINAL SHUTDOWN AND BINDINGS ==='
    pin_low || rc=1
    [ -L "$AMP/driver" ] || rc=1
    [ -L "$CARD/driver" ] || rc=1
    [ "$(cat "/sys/module/$MOD/parameters/allow_activation" 2>/dev/null)" = N ] || rc=1
    if [ "$rc" -eq 0 ]; then
        echo 'PASS: E9 pulse completed; E4E restored; activation disabled'
    else
        echo 'ERROR: test or restoration incomplete; inspect pin and modules before retrying' >&2
    fi
    exit "$rc"
}
trap restore EXIT
trap 'exit 130' INT
trap 'exit 129' HUP
trap 'exit 143' TERM

echo '=== STRICT PREFLIGHT ==='
[ "$(modinfo -F description "$NEW")" = 'SM-T575 E9 one-shot PCM-triggered 500ms audible diagnostic' ] || { echo 'ERROR: unexpected E9 module' >&2; exit 1; }
[ "$#" -eq 1 ] && [ "$(printf %s "$EXPECTED_NEW_SHA" | wc -c)" -eq 64 ]
[ "$(uname -r)" = 7.3.0 ]
[ -s "$OLD" ] && [ -s "$NEW" ] && [ -s "$TONE" ]
[ "$(sha256sum "$OLD" | cut -d ' ' -f 1)" = 24154adb80bfebd56dd76cc18b269d1fcedf7a33f4ac3785a1c797458fd650ab ]
[ "$(sha256sum "$NEW" | cut -d ' ' -f 1)" = "$EXPECTED_NEW_SHA" ]
[ "$(modinfo -F vermagic "$NEW" | cut -d ' ' -f 1)" = 7.3.0 ]
[ "$(cat "/sys/module/$MOD/parameters/allow_activation")" = N ]
[ -L "$AMP/driver" ] && [ -L "$CARD/driver" ]
pin_low
for dev in /dev/snd/pcmC0D0p /dev/snd/pcmC0D1p /dev/snd/pcmC0D0c; do
    if [ -e "$dev" ] && fuser -s "$dev" 2>/dev/null; then
        echo "ERROR: PCM device busy: $dev" >&2
        exit 1
    fi
done

echo '=== REPLACE MODULE WITH ONE-SHOT ENABLED BUILD ==='
TOUCHED=1
printf 'sound' > "$TRANSPORT/unbind"
pin_low
printf '4-004c' > "$CODEC/unbind"
pin_low
rmmod "$MOD"
pin_low
insmod "$NEW" allow_activation=1
[ -L "$AMP/driver" ]
pin_low
[ "$(cat "/sys/module/$MOD/parameters/allow_activation")" = Y ]
printf 'sound' > "$TRANSPORT/bind"
[ -L "$CARD/driver" ]
pin_low

echo '=== START 2-SECOND QUIET PCM (E9 ACTIVATES ON START) ==='
aplay -q -D hw:0,1 -t raw -f S32_LE -r 48000 -c 2 "$TONE" \
    >/home/Xnopish/t575-audio-stage-e9/aplay.log 2>&1 &
PCM_PID=$!
wait "$PCM_PID"
PCM_PID=
pin_low
grep -x closed /proc/asound/card0/pcm1p/sub0/status

echo '=== E9 DRIVER RESULT ==='
dmesg | grep -E 'E9: (one-shot PCM-triggered|pulse |PCM closed)|E4D: bounded active test' | tail -15
dmesg | grep -q 'E9: one-shot PCM-triggered 500ms low-level pulse BEGIN'
dmesg | grep -q 'E4D: bounded active test started'
dmesg | grep -q 'E4D: bounded active test completed'
dmesg | grep -q 'E9: pulse COMPLETE; amplifier OFF'
pin_low
echo 'PASS: E9 PCM-triggered bounded audible pulse returned amplifier OFF'
