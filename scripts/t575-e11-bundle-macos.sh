#!/bin/bash
# Stage E11 desktop routing on owner's SM-T575 over configured SSH.
# No kernel module change, no root, no amplifier activation.
set -euo pipefail
REPO=Forenzo/samsung-gtactive3LTE
BASE=https://raw.githubusercontent.com/$REPO/work/t575-native-install/scripts
OUT="$HOME/Downloads/T575-E11-Routing"
mkdir -p "$OUT"
for name in t575-e11-audio-route.sh t575-e11-install.sh; do
    curl -fsSL "$BASE/$name" -o "$OUT/$name"
    test -s "$OUT/$name"
done
echo '=== TRANSFER E11 USER ROUTING ==='
ssh active3 'mkdir -p ~/t575-audio-stage-e11'
scp "$OUT/t575-e11-audio-route.sh" "$OUT/t575-e11-install.sh" \
    active3:~/t575-audio-stage-e11/
echo '=== INSTALL E11 USER ROUTING ==='
ssh active3 'sh ~/t575-audio-stage-e11/t575-e11-install.sh'
echo '=== E11 ROUTING READY ==='
echo 'Headphones: ssh active3 "~/.local/bin/t575-audio-route headphones"'
echo 'Status: ssh active3 "~/.local/bin/t575-audio-route status"'
echo 'The TAS2562 amplifier remains disabled under E4E.'
