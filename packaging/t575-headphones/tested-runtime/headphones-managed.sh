#!/bin/sh
set -eu

PATH=/usr/sbin:/usr/bin:/sbin:/bin
DIR=/etc/t575-headphones
MOD="$DIR/snd-soc-rt5665.ko"
ROLLBACK="$DIR/rollback-v2.sh"
FLAG=/run/t575-rt5665-test.active
P=/sys/bus/platform/drivers/gtactive3lte-transport64
I=/sys/bus/i2c/drivers/rt5665
S=/sys/module/t575_tas2562_safeactive/parameters/allow_activation

EXPECTED=792866896625a515557116768b108f3e26dfc9997928fa1777720557d8d83907

echo "=== STRICT PREFLIGHT ==="

test "$(id -u)" = 0
test "$(uname -r)" = 7.3.0
test "$(cat "$S")" = N
test -L "$P/sound"
test -L "$I/3-001b"
test ! -e "$FLAG"
test -s "$MOD"
test -s "$ROLLBACK"

sh -n "$ROLLBACK"

ACTUAL=$(sha256sum "$MOD" | cut -d " " -f 1)
test "$ACTUAL" = "$EXPECTED"

test "$(modinfo -F vermagic "$MOD")" = \
     "$(modinfo -F vermagic snd_soc_rt5665)"

grep -q '^snd_soc_rt5665 ' /proc/modules
grep -q 'Active3' /proc/asound/cards

echo "PASS: module SHA256 and kernel ABI"
echo "PASS: original soundcard bound"
echo "PASS: speaker amplifier locked"
echo "PASS: rollback script available"

if [ "${1:-}" = "--check" ]; then
    echo "PREFLIGHT ONLY — NO CHANGES"
    exit 0
fi

if [ "${1:-}" != "--run" ]; then
    echo "Usage: test-switch.sh --check or --run"
    exit 1
fi

echo "=== MANAGED HEADPHONE SESSION ==="
test -f /usr/share/alsa/ucm2/conf.d/Galaxy_Tab_Acti/HiFi.conf || {
    echo "BLOCKED: LTE headphone UCM missing"
    exit 1
}
echo "Recovery: EXIT trap and systemd ExecStopPost"

PHASE=pre_detach
touch "$FLAG"

recover_on_exit() {
    result=$?
    trap - EXIT

    if [ "$PHASE" = pre_detach ]; then
        echo "=== EARLY EXIT: RESTORE AUDIO ONLY ==="

        sudo -u __AUDIO_LOGIN__ env \
          XDG_RUNTIME_DIR=/run/user/__AUDIO_UID__ \
          DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/__AUDIO_UID__/bus \
          systemctl --user start \
            pipewire.socket pipewire-pulse.socket || true

        sudo -u __AUDIO_LOGIN__ env \
          XDG_RUNTIME_DIR=/run/user/__AUDIO_UID__ \
          DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/__AUDIO_UID__/bus \
          systemctl --user start \
            pipewire.service pipewire-pulse.service \
            wireplumber.service || true

        rm -f "$FLAG"
        echo "Original kernel drivers were not detached"
    else
        echo "=== DRIVER SWITCH BEGAN: RUN ROLLBACK ==="
        /bin/sh "$ROLLBACK" ||
          echo "ERROR: rollback requires manual inspection"
    fi

    exit "$result"
}

trap 'recover_on_exit' EXIT
trap 'exit 143' TERM
trap 'exit 130' INT
trap 'exit 129' HUP

echo "=== KEEP PHOSH AUDIO SERVER RUNNING ==="
for unit in pipewire.service pipewire-pulse.service \
    pipewire.socket pipewire-pulse.socket
do
    sudo -u __AUDIO_LOGIN__ env \
      XDG_RUNTIME_DIR=/run/user/__AUDIO_UID__ \
      DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/__AUDIO_UID__/bus \
      systemctl --user is-active --quiet "$unit" || {
        echo "BLOCKED: audio server not active: $unit"
        exit 1
    }
done

echo "=== RELEASE ALSA VIA WIREPLUMBER ONLY ==="
sudo -u __AUDIO_LOGIN__ env \
  XDG_RUNTIME_DIR=/run/user/__AUDIO_UID__ \
  DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/__AUDIO_UID__/bus \
  systemctl --user stop wireplumber.service

sleep 2

echo "=== VERIFY ALSA RELEASED ==="
if fuser /dev/snd/* 2>/dev/null; then
    echo "BLOCKED: ALSA still in use"
    exit 1
fi

test "$(cat "$S")" = N
echo "PASS: ALSA released; Pulse server kept running"

echo "=== DETACH ORIGINAL CODEC ==="
PHASE=detaching
printf 'sound\n' > "$P/unbind"
printf '3-001b\n' > "$I/unbind"
rmmod snd_soc_rt5665

echo "=== LOAD RECOVERY CODEC ==="
insmod "$MOD"

if [ ! -L "$I/3-001b" ]; then
    printf '3-001b\n' > "$I/bind"
fi

printf 'sound\n' > "$P/bind"

echo "=== VERIFY EXPERIMENTAL SOUNDCARD ==="
cat /proc/asound/cards
test "$(cat "$S")" = N

echo "=== WAIT FOR RT5665 CALIBRATION ==="
sleep 3
test "$(cat "$S")" = N
echo "PASS: calibration settling interval complete"

echo "=== ENABLE HEADPHONE ROUTE ==="
test "$(cat "$S")" = N

amixer -c 0 sset "Stereo1 DAC MIXL DAC L1" on
amixer -c 0 sset "Stereo1 DAC MIXR DAC R1" on
amixer -c 0 sset "HPO" on
amixer -c 0 sset "Headphone" 5

echo "=== VERIFY HEADPHONE MIXERS ==="
for control in     "Stereo1 DAC MIXL DAC L1"     "Stereo1 DAC MIXR DAC R1"     "HPO"     "Headphone"
do
    echo "--- $control ---"
    amixer -c 0 sget "$control" | tail -n 5
done

test "$(cat "$S")" = N

echo "=== VERIFY ROUTE BEFORE PLAYBACK ==="

for control in     "Stereo1 DAC MIXL DAC L1"     "Stereo1 DAC MIXR DAC R1"     "HPO"
do
    if ! amixer -c 0 sget "$control" |
         grep -q "Playback \[on\]"; then
        echo "BLOCKED: mixer not enabled: $control"
        exit 1
    fi
done

echo "PASS: headphone route enabled"
test "$(cat "$S")" = N


echo "=== START DESKTOP AUDIO MANAGEMENT ==="

as_user() {
    sudo -u __AUDIO_LOGIN__ env \
      XDG_RUNTIME_DIR=/run/user/__AUDIO_UID__ \
      DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/__AUDIO_UID__/bus \
      "$@"
}

as_user systemctl --user start wireplumber.service

echo "=== WAIT FOR PIPEWIRE HEADPHONE SINK ==="
READY=0
for attempt in 1 2 3 4 5 6 7 8 9 10; do
    if as_user pactl list short sinks |
        grep -q "alsa_output.platform-sound.HiFi__Headphones__sink"; then
        READY=1
        break
    fi
    sleep 1
done

test "$READY" = 1 || {
    echo "BLOCKED: headphone sink missing"
    exit 1
}

echo "=== REAPPLY HEADPHONE ROUTE ==="
test "$(cat "$S")" = N

amixer -c 0 sset "Stereo1 DAC MIXL DAC L1" on >/dev/null
amixer -c 0 sset "Stereo1 DAC MIXR DAC R1" on >/dev/null
amixer -c 0 sset "Headphones" on >/dev/null
amixer -c 0 sset "HPO" on >/dev/null
amixer -c 0 sset "Headphone" 3 >/dev/null

echo "=== SELECT HEADPHONE OUTPUT ==="
as_user pactl set-default-sink \
    alsa_output.platform-sound.HiFi__Headphones__sink
as_user pactl set-sink-mute \
    alsa_output.platform-sound.HiFi__Headphones__sink 0
as_user pactl set-sink-volume \
    alsa_output.platform-sound.HiFi__Headphones__sink 20%

test "$(cat "$S")" = N

echo "=== HEADPHONE PLAYBACK SESSION ==="
echo "PLAY YOUR VIDEO IN LIBREWOLF NOW"
echo "Continuous managed listening session"
echo "Stop t575-headphones.service to restore the original driver"

while :; do
    sleep 3600
 done

echo "=== END VIDEO TEST ==="
test "$(cat "$S")" = N

echo "=== RESTORE ORIGINAL CODEC ==="
/bin/sh "$ROLLBACK"

trap - EXIT

echo "=== FINAL VERIFICATION ==="
test ! -e "$FLAG"
test -L "$P/sound"
test -L "$I/3-001b"
test "$(cat "$S")" = N

cat /proc/asound/cards
echo "TEST COMPLETED — ORIGINAL DRIVER RESTORED"
