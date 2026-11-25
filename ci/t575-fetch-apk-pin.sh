#!/bin/bash
set -euo pipefail

D=$(cd "${1:?Specify prepared Duranium directory}" && pwd)

test "$(uname -m)" = x86_64

NAME=apk-tools-static-3.0.9-r0.apk

OLD=677dddb435ca7d621ce9f8a1a404a4cedc631651fd025893c548c34a4ceecb19

EXPECTED=0a1a0682375f66a83b7b903f6e4638ccfe312547d50d336b5f2be9fc391281be

URL="https://dl-cdn.alpinelinux.org/alpine/v3.24/main/x86_64/$NAME"

DEST="$D/apk-pin"

mkdir -p "$DEST"

TEMP=$(mktemp -d "$DEST/verify.XXXXXX")

trap 'rm -rf "$TEMP"' EXIT

echo "=== DOWNLOAD PINNED ALPINE 3.24 PACKAGE ==="

curl -fsSL --retry 3 \
    --connect-timeout 15 \
    --max-time 120 \
    -o "$TEMP/$NAME" "$URL"

printf '%s  %s\n' "$EXPECTED" "$TEMP/$NAME" |
    sha256sum -c -

echo "=== VERIFY OFFICIAL ALPINE PACKAGE SIGNATURE ==="

docker pull --platform linux/amd64 docker.io/library/alpine:3.24

VERIFIER=$(docker image inspect \
    --format '{{index .RepoDigests 0}}' \
    docker.io/library/alpine:3.24)

[[ "$VERIFIER" =~ @sha256:[a-f0-9]{64}$ ]]

docker run --rm \
    --platform linux/amd64 \
    --network none \
    -v "$TEMP:/audit:ro" \
    "$VERIFIER" \
    apk verify "/audit/$NAME"

echo "PASS: Alpine package signature verified"

mv "$TEMP/$NAME" "$DEST/$NAME"

echo "=== ADAPT PREPARED IMAGE BUILDER ==="

python3 - "$D" "$OLD" "$EXPECTED" <<'PY'
from pathlib import Path
import sys

d = Path(sys.argv[1])
old = sys.argv[2]
new = sys.argv[3]

p = d / "contrib/samsung-gtactive3/build-image.sh"

s = p.read_text()

assert s.count(old) == 1
assert "APK_PIN=${APK_PIN-3.0.9-r0}" in s

s = s.replace(old, new, 1)

p.write_text(s)

print("PASS: authenticated stable package checksum installed")
print("PASS: APK Tools version remains 3.0.9-r0")
PY

sh -n "$D/contrib/samsung-gtactive3/build-image.sh"

cat > "$DEST/PROVENANCE" <<EOF
PACKAGE=$NAME
SOURCE=$URL
SHA256=$EXPECTED
ORIGINAL_EDGE_SHA256=$OLD
VERIFIER_IMAGE=$VERIFIER
SIGNATURE_VERIFIED=yes
EOF

cat "$DEST/PROVENANCE"

echo "PASS: authenticated compatibility package ready"
