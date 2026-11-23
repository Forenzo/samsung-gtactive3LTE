#!/bin/sh
# E10 staging audit, no kernel or mixer writes.
set -eu
D=/home/Xnopish/t575-audio-stage-e10
U=/usr/share/alsa/ucm2/conf.d/gtactive3
echo '=== E10 MODULE METADATA ==='
test "$(uname -r)" = 7.3.0
test -s "$D/t575-tas2562-safeactive.ko"
test "$(modinfo -F description "$D/t575-tas2562-safeactive.ko")" = 'SM-T575 E10 bounded 2s PCM speaker preview - opt-in only'
modinfo -F vermagic "$D/t575-tas2562-safeactive.ko"
sha256sum "$D/t575-tas2562-safeactive.ko" | tee "$D/module.sha256"
echo '=== PRESERVE INSTALLED WORKING HEADPHONE UCM ==='
test -s "$U/HiFi.conf"
test -s "$U/gtactive3.conf"
mkdir -p "$D/headset-ucm"
cp "$U/HiFi.conf" "$D/headset-ucm/HiFi.conf"
cp "$U/gtactive3.conf" "$D/headset-ucm/gtactive3.conf"
grep -q "SectionDevice.\"Headphones\"" "$D/headset-ucm/HiFi.conf"
grep -q "PlaybackPCM \"hw:\${CardId},0\"" "$D/headset-ucm/HiFi.conf"
sha256sum "$D/headset-ucm/"*.conf | tee "$D/headset-ucm/sha256.txt"
echo '=== PRESERVE PIPEWIRE USER CONFIGURATION ==='
P="$HOME/.config/pipewire/pipewire-pulse.conf.d/90-t575-speaker.conf"
test -s "$P"
cp "$P" "$D/headset-ucm/90-t575-speaker.conf"
echo '=== CHECK BASELINE ==='
test "$(cat /proc/asound/card0/id)" = Active3
grep -q "^t575_tas2562_safeactive " /proc/modules
test -s "$D/t575-e10-preview-test.sh"
echo 'PASS: E10 module and existing RT5665 UCM/headset bundle staged'
echo 'NO AUDIO MODULES CHANGED; NO SPEAKER ACTIVATION; NO SYSTEM FILES MODIFIED'
