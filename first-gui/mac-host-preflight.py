#!/usr/bin/env python3
"""Read-only macOS checks for an SM-T575 host-served Plasma root filesystem.

Usage:
  python3 first-gui/mac-host-preflight.py /path/to/plasma-artifact.zip

Does not extract, export, mount, start nfsd, configure networking, or touch
the tablet. Probes only the existing TCP diagnostic console handshake.
"""
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import zipfile

GUEST = "fe80::57:aff:fe00:1"
MIN_FREE = 4 * 1024 ** 3


def interfaces():
    try:
        output = subprocess.check_output(
            ["ifconfig", "-l"], text=True, timeout=5
        )
        return output.split()
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return []


def probe(interface):
    try:
        with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as sock:
            sock.settimeout(2)
            sock.connect((GUEST, 23, 0, socket.if_nametoindex(interface)))
            data = bytearray()
            while len(data) < 16384:
                part = sock.recv(4096)
                if not part:
                    break
                data.extend(part)
                if b"\n> " in data:
                    break
            return bytes(data)
    except (OSError, TimeoutError):
        return None


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: python3 first-gui/mac-host-preflight.py /path/to/artifact.zip")
    if sys.platform != "darwin":
        sys.exit("This preflight targets macOS only.")
    path = Path(sys.argv[1]).expanduser()
    print("=== Plasma Mobile Mac host preflight (READ ONLY) ===", flush=True)

    if not path.is_file():
        sys.exit(f"FAIL: archive not found: {path}")
    try:
        with zipfile.ZipFile(path) as archive:
            needed = {
                "SHA256SUMS",
                "packages-aarch64.txt",
                "t575-plasma-userspace-aarch64.tar.gz",
            }
            missing = needed - set(archive.namelist())
            if missing:
                sys.exit(f"FAIL: missing archive members: {sorted(missing)}")
    except zipfile.BadZipFile as exc:
        sys.exit(f"FAIL: invalid ZIP: {exc}")
    print("Artifact ZIP layout: PASS (run host-audit-plasma.py separately for SHA256)")

    free = shutil.disk_usage(path.parent).free
    print(f"Free disk space near artifact: {free / 1024 ** 3:.2f} GiB")
    if free < MIN_FREE:
        print("WARNING: less than 4 GiB free; do not stage the root filesystem.")

    nfsd = shutil.which("nfsd")
    print("macOS nfsd installed:", nfsd or "not found")
    print("Export state: unchanged; no server started.")

    candidates = [i for i in interfaces() if i.startswith(("en", "bridge"))]
    found = []
    for interface in candidates:
        data = probe(interface)
        if data and b"> " in data:
            found.append(interface)
    if found:
        print("Tablet diagnostic console reachable via:", ", ".join(found))
    else:
        print("Tablet diagnostic console not reached; check USB cable and boot.")
    print("No mount, extraction, service change, or tablet write performed.")
    print("Host checks complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
