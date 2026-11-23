#!/bin/sh
# E11 safe user-only installation; never enable TAS2562 speaker.
set -eu
D=/home/Xnopish/t575-audio-stage-e11
R="$D/t575-e11-audio-route.sh"
BASE="$HOME/.local"
UCMD="$HOME/t575-audio-stage-e10/headset-ucm"
P="$HOME/.config/pipewire/pipewire-pulse.conf.d/90-t575-speaker.conf"
die(){ echo "ERROR: $*" >&2; exit 1; }
[ "$(id -u)" != 0 ] || die "Run unprivileged as Xnopish"
[ -s "$R" ] || die "Missing staged E11 routing script"
[ -s "$UCMD/HiFi.conf" ] && [ -s "$UCMD/gtactive3.conf" ] || die "Previous RT5665 backup not present"
[ -s "$P" ] || die "Existing PipeWire speaker sink configuration missing"
command -v pactl >/dev/null || die "pactl missing"
pactl info >/dev/null 2>&1 || die "PipeWire Pulse unavailable"
[ -f /sys/module/t575_tas2562_safeactive/parameters/allow_activation ] || die "TAS2562 safety state unavailable"
echo '=== E11 ROUTE INSTALL (USER-ONLY) ==='
mkdir -p "$BASE/bin" "$BASE/share/t575-audio/e11"
if [ -e "$BASE/bin/t575-audio-route" ]; then
  cp "$BASE/bin/t575-audio-route" "$BASE/share/t575-audio/e11/previous-route.sh"
fi
cp "$R" "$BASE/bin/t575-audio-route"
chmod 755 "$BASE/bin/t575-audio-route"
cp "$UCMD/HiFi.conf" "$BASE/share/t575-audio/e11/HiFi.conf"
cp "$UCMD/gtactive3.conf" "$BASE/share/t575-audio/e11/gtactive3.conf"
cp "$P" "$BASE/share/t575-audio/e11/90-t575-speaker.conf"
sha256sum "$BASE/share/t575-audio/e11/"*.conf > "$BASE/share/t575-audio/e11/manifest.sha256"
echo '=== AUDIO ROUTES ==='
"$BASE/bin/t575-audio-route" status
echo '=== SELECT HEADSET (KNOWN-GOOD PATH) ==='
"$BASE/bin/t575-audio-route" headphones
echo '=== INSTALL RESULT ==='
echo 'PASS: E11 user-level route installed; RT5665 preserved, E4E unchanged'
echo 'NOTE: speaker intentionally remains locked pending continuously-safe TAS2562 runtime'
