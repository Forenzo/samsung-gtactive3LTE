#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Run ON THE TABLET in an interactive terminal with sudo access.
# Capture text-only copies of the exact PROVEN protected headphone controllers.
# This does not change the live audio service or kernel modules.
# Review before publishing: scripts and logs can contain host-specific details.
set -euo pipefail

[[ "$(id -u)" -ne 0 ]] || {
  echo "Run as the normal login user; sudo only for reading protected files." >&2
  exit 1
}
command -v sudo >/dev/null
sudo -v

safety=/sys/module/t575_tas2562_safeactive/parameters/allow_activation
[[ "$(sudo cat "$safety")" == N ]] || {
  echo "BLOCKED: TAS2562 safety lock not N" >&2
  exit 1
}

src=/etc/t575-headphones
out="${1:-$HOME/t575-headphone-runtime-capture}"

case "$out" in
  "$HOME"/*) ;;
  *) echo "Output must be an absolute path inside your HOME directory" >&2; exit 2 ;;
esac
[[ ! -e "$out" ]] || {
  echo "Refusing to overwrite: $out" >&2
  exit 1
}
umask 077
mkdir -m 700 "$out"

for name in headphones-managed.sh rollback-v2.sh t575-headphones.service; do
  sudo test -f "$src/$name"
  sudo cat "$src/$name" > "$out/$name"
  chmod 600 "$out/$name"
  echo "Captured $name"
done

# Capture installed unit too, in case it differs from the staged reference.
sudo cat /etc/systemd/system/t575-headphones.service \
  > "$out/t575-headphones.installed.service"
chmod 600 "$out/t575-headphones.installed.service"

# Record a verifiable checksum without copying/distributing the binary.
sudo sha256sum "$src/snd-soc-rt5665.ko" \
  > "$out/patched-module.sha256"
chmod 600 "$out/patched-module.sha256"

sha256sum "$out"/*.sh "$out"/*.service > "$out/captured-text.sha256"

echo
echo "=== RESULT ==="
echo "Private text capture saved to $out"
echo "Driver module itself NOT copied"
echo "Audio service NOT restarted or stopped"
echo "No system files modified"
echo "NEXT: inspect all captured contents for secrets, paths and personal data"
echo "Only after review, commit the final controller scripts to the reproduction branch"
