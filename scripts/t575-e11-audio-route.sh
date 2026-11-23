#!/bin/sh
# SM-T575 E11: non-destructive desktop audio route manager.
# Does not load modules, change ALSA mixers, or touch /usr.
set -eu
SPEAKER=t575_speaker
HEADSET=alsa_output.platform-sound.stereo-fallback
AMP=/sys/module/t575_tas2562_safeactive/parameters/allow_activation

fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
need_pulse() { command -v pactl >/dev/null 2>&1 || fail "pactl missing"; pactl info >/dev/null 2>&1 || fail "PipeWire Pulse unavailable"; }
find_headset() {
    if pactl list short sinks | awk -v n="$HEADSET" '$2==n{found=1} END{exit !found}'; then
        echo "$HEADSET"
        return
    fi
    names=$(pactl list short sinks | awk '$2!="t575_speaker" && $2 ~ /^alsa_output\./ {print $2}')
    count=$(printf '%s\n' "$names" | grep -c . || true)
    [ "$count" -eq 1 ] || fail "Cannot uniquely identify RT5665 headset sink; inspect pactl list short sinks"
    printf '%s\n' "$names"
}
[ "$#" -gt 0 ] || set -- status
case "$1" in
    status)
        need_pulse
        printf '%s\n' '=== T575 DESKTOP AUDIO ==='
        pactl info | grep -E '^Default Sink:' || true
        pactl list short sinks
        printf '%s\n' '=== SPEAKER LOCKOUT ==='
        if [ -r "$AMP" ]; then
            printf 'Activation permission: '; cat "$AMP"
        else
            printf '%s\n' 'Activation permission: root-only; not queried'
        fi
        printf '%s\n' '=== HEADSET JACK PORT INFO (IF AVAILABLE) ==='
        pactl list sinks | grep -E -A 7 'Ports:|analog-output-headphones|Headphones' | head -65 || true
        ;;
    headphones)
        need_pulse
        target=$(find_headset)
        pactl set-default-sink "$target"
        printf 'PASS: default audio sink switched to headset: %s\n' "$target"
        ;;
    speaker)
        need_pulse
        [ -r "$AMP" ] || fail "Cannot verify amplifier status. Speaker routing not enabled."
        [ "$(cat "$AMP")" = "Y" ] || fail "E4E has amplifier disabled. Speaker default withheld to prevent silent output."
        fail "E10 runtime is diagnostic only: continuous speaker selection not yet supported."
        ;;
    *)
        printf 'Usage: %s [status|headphones|speaker]\n' "$0" >&2
        exit 2
        ;;
esac
