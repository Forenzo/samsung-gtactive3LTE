#!/bin/sh
# SM-T575 E8D lifecycle-only event test. NO AMPLIFIER ACTIVATION.
# Run as root after stopping PipeWire/WirePlumber. E4E restored on exit.
set -eu
OLD=/home/Xnopish/t575-audio-stage-e4e/t575-tas2562-safeactive.ko
NEW=/home/Xnopish/t575-audio-stage-e8d/t575-tas2562-safeactive.ko
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
        echo 'PASS: E8D event test completed, E4E restored, amplifier OFF'
    else
        echo 'FAIL: inspect module bindings and SDZ before doing anything else' >&2
    fi
    exit "$rc"
}
trap restoration EXIT
trap 'exit 130' INT
trap 'exit 129' HUP
trap 'exit 143' TERM

echo '=== E8D STRICT PREFLIGHT ==='
[ "$(modinfo -F description "$NEW")" = 'SM-T575 E8D mock in-flight STOP test; TAS2562 always OFF' ] || { echo 'FAIL: unexpected module description' >&2; exit 1; }
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

echo '=== E8D LOCKED REPLACE (AMP ALWAYS OFF) ==='
TOUCHED=1
printf sound > "$TRANSPORT/unbind"
pin_low
printf 4-004c > "$CODEC/unbind"
pin_low
rmmod "$MOD"
pin_low
insmod "$NEW" simulate_activation=1
pin_low
[ -L "$AMP/driver" ]
[ "$(cat /sys/module/$MOD/parameters/simulate_activation)" = Y ]
printf sound > "$TRANSPORT/bind"
[ -L "$CARD/driver" ]
pin_low

echo '=== E8D START MOCK WORKER; INTERRUPT PCM ==='
aplay -q -D hw:0,1 -t raw -f S32_LE -r 48000 -c 2 "$TONE" \
  >/home/Xnopish/t575-audio-stage-e8d/aplay-interrupted.log 2>&1 &
PCM_PID=$!

FOUND=0
i=0
while [ "$i" -lt 40 ]; do
    if dmesg | grep -q 'E8D: mock initialization BEGIN; amplifier OFF'; then
        FOUND=1
        break
    fi
    kill -0 "$PCM_PID" 2>/dev/null || break
    sleep 0.025
    i=$((i + 1))
done
[ "$FOUND" -eq 1 ] || { echo 'FAIL: mock worker did not begin' >&2; exit 1; }
echo '=== REQUEST PCM STOP WHILE MOCK WORKER RUNNING ==='
kill -TERM "$PCM_PID" 2>/dev/null || true
wait "$PCM_PID" 2>/dev/null || true
PCM_PID=
pin_low
grep -x closed /proc/asound/card0/pcm1p/sub0/status

echo '=== VERIFY MOCK WORKER ABORT ==='
dmesg | grep 'E8D:' | tail -15
dmesg | grep -q 'E8D: STOP latched; amplifier OFF'
dmesg | grep -q 'E8D: mock initialization ABORTED; amplifier OFF'
if dmesg | grep -q 'E8D: mock initialization FINISHED'; then
    echo 'FAIL: mock worker finished rather than aborted' >&2
    exit 1
fi

echo '=== SECOND PCM START MUST BE DENIED ==='
aplay -q -D hw:0,1 -t raw -f S32_LE -r 48000 -c 2 "$TONE" \
  >/home/Xnopish/t575-audio-stage-e8d/aplay-second.log 2>&1 &
PCM_PID=$!
wait "$PCM_PID"
PCM_PID=
dmesg | grep 'E8D:' | tail -15
dmesg | grep -q 'E8D: second START DENIED by abort latch; amplifier OFF'
pin_low
grep -x closed /proc/asound/card0/pcm1p/sub0/status
echo 'PASS: E8D mock worker interrupted, second activation denied, SDZ LOW'
