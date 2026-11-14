#!/bin/sh
# Read-only checks, intended for the future RAM-only GUI environment.
set -eu

echo '=== First-GUI userspace preflight (does not start a compositor) ==='
uname -m
echo '=== Binaries ==='
for bin in weston seatd udevadm; do
  command -v "$bin" || { echo "Missing $bin" >&2; exit 1; }
done
echo '=== Weston version ==='
weston --version
echo '=== DRM nodes ==='
if [ -d /dev/dri ]; then ls -l /dev/dri; else echo 'No /dev/dri on this host (expected in CI)'; fi
echo '=== Input nodes ==='
if [ -d /dev/input ]; then ls -l /dev/input; else echo 'No /dev/input on this host (expected in CI)'; fi
echo '=== No actual display launch in this preflight ==='
