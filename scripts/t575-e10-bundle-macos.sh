#!/bin/bash
# Fetch E10 CI artifact, stage module and preserve headset configuration.
# Runs on owner's Mac. NO kernel changes and no amplifier activation.
set -euo pipefail
RUN_ID="${1:?Usage: $0 <successful E10 Actions run id>}"
REPO=Forenzo/samsung-gtactive3LTE
DEST="$HOME/Downloads/T575-E10-Bundle-$RUN_ID"
REMOTE=/home/Xnopish/t575-audio-stage-e10
mkdir -p "$DEST"
test ! -e "$DEST/t575-tas2562-safeactive.ko" || {
  echo "Module already downloaded: use a new destination; refusing overwrite" >&2
  exit 1
}
echo "=== DOWNLOAD E10 COMPILE ARTIFACT ==="
gh run download "$RUN_ID" --repo "$REPO" \
  --name t575-e10-preview-COMPILE-ONLY --dir "$DEST"
echo "=== DOWNLOAD TEST AND STAGING SCRIPTS ==="
for f in t575-e10-preview-test.sh t575-e10-tablet-stage.sh; do
  curl -fsSL "https://raw.githubusercontent.com/$REPO/work/t575-native-install/scripts/$f" \
    -o "$DEST/$f"
done
test -s "$DEST/t575-tas2562-safeactive.ko"
test -s "$DEST/t575-e10-preview-test.sh"
echo "=== COPY E10 TO TABLET (NO INSTALL) ==="
ssh active3 "mkdir -p '$REMOTE'"
scp "$DEST/t575-tas2562-safeactive.ko" \
  "$DEST/t575-e10-preview-test.sh" \
  "$DEST/t575-e10-tablet-stage.sh" \
  "active3:$REMOTE/"
ssh active3 "sh '$REMOTE/t575-e10-tablet-stage.sh'"
echo "=== STAGED; NOT ACTIVATED ==="
