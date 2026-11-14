#!/usr/bin/env python3
"""Inspect downloaded GitHub Actions Plasma archive without extracting or running it.

Works on macOS and Linux; no shell commands, root privileges or device writes.
Pass the *GitHub artifact ZIP* containing
  t575-plasma-userspace-aarch64.tar.gz
  SHA256SUMS
  packages-aarch64.txt
or a directory with those files.
"""
from pathlib import Path, PurePosixPath
import hashlib
import io
import sys
import tarfile
import zipfile

if len(sys.argv) != 2:
    sys.exit("Usage: python3 first-gui/host-audit-plasma.py /path/to/artifact.zip")

path = Path(sys.argv[1])
if path.is_dir():
    manifest = (path / "SHA256SUMS").read_text()
    package_list = (path / "packages-aarch64.txt").read_text()
    tfile = path / "t575-plasma-userspace-aarch64.tar.gz"
    expected = tfile.stat().st_size
    digest = hashlib.sha256(tfile.read_bytes()).hexdigest()
    tar_source = tfile
else:
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        required = {"SHA256SUMS", "packages-aarch64.txt",
                    "t575-plasma-userspace-aarch64.tar.gz"}
        missing = required - names
        if missing:
            sys.exit(f"Artifact is missing {sorted(missing)}")
        manifest = z.read("SHA256SUMS").decode()
        package_list = z.read("packages-aarch64.txt").decode()
        data = z.read("t575-plasma-userspace-aarch64.tar.gz")
    expected = len(data)
    digest = hashlib.sha256(data).hexdigest()
    tar_source = io.BytesIO(data)

checksum_line = [x for x in manifest.splitlines()
                 if x.strip().endswith("t575-plasma-userspace-aarch64.tar.gz")]
if len(checksum_line) != 1 or checksum_line[0].split()[0] != digest:
    sys.exit("FAIL: userspace SHA256 does not match the CI manifest")
print("SHA256 OK:", digest)
print("Compressed archive bytes:", expected)
print("Package-manifest entries:", len(package_list.splitlines()))

with tarfile.open(fileobj=tar_source if not isinstance(tar_source, Path) else None,
                  name=str(tar_source) if isinstance(tar_source, Path) else None,
                  mode="r:gz") as tf:
    seen = set()
    total = 0
    unsafe = []
    for member in tf:
        pure = PurePosixPath(member.name)
        if pure.is_absolute() or ".." in pure.parts:
            unsafe.append(member.name)
        if member.isdev() or member.isfifo():
            # Device nodes / pipes should not be restored on the Mac host.
            pass
        total += member.size
        seen.add(str(pure).removeprefix("./"))
    if unsafe:
        sys.exit(f"FAIL: unsafe archive members: {unsafe[:8]}")
    for name in ("usr/bin/kwin_wayland", "usr/bin/startplasma-wayland",
                 "usr/share/wayland-sessions/plasma-mobile.desktop"):
        if name not in seen:
            sys.exit(f"FAIL: missing required graphical component {name}")
print("Uncompressed member bytes:", total)
print("Plasma Mobile executable and session files: PRESENT")
print("Inspection only. No extraction, no NFS export and NO tablet changes.")
