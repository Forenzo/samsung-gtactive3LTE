#!/usr/bin/env python3
"""Safely add a small Alpine AArch64 Cage compositor overlay to the Mac NFS tree.

Only creates *missing* /usr and /lib package files on the Mac's mounted
/Volumes/T575-Plasma/rootfs. Existing files must match exactly or the
installation aborts BEFORE writing. Never accesses Android partitions.
Run from the extracted overlay kit as:
  sudo python3 install-t575-cage-overlay.py t575-cage-overlay-aarch64.tar.gz
"""
from pathlib import Path, PurePosixPath
import hashlib
import os
import stat
import sys
import tarfile

ROOT = Path("/Volumes/T575-Plasma/rootfs")
ARCHIVE_NAME = "t575-cage-overlay-aarch64.tar.gz"

def fail(message):
    raise RuntimeError(message)

def entry_name(member):
    p = PurePosixPath(member.name)
    if p.is_absolute() or ".." in p.parts or not p.parts:
        fail(f"Unsafe archive path: {member.name}")
    if p.parts[0] not in ("usr", "lib") or len(p.parts) < 2:
        fail(f"Unexpected path outside /usr or /lib: {member.name}")
    return str(p)

def same_content(target, tf, member):
    if target.is_symlink() or not target.is_file() or target.stat().st_size != member.size:
        return False
    a = hashlib.sha256()
    b = hashlib.sha256()
    with target.open("rb") as existing:
        while chunk := existing.read(1024 * 1024):
            a.update(chunk)
    source = tf.extractfile(member)
    if source is None: return False
    with source:
        while chunk := source.read(1024 * 1024):
            b.update(chunk)
    return a.digest() == b.digest()

def main():
    if sys.platform != "darwin": fail("This installer is for the macOS NFS host")
    if os.geteuid() != 0: fail("Run with sudo so Linux file modes are preserved")
    if len(sys.argv) != 2: fail("Usage: sudo python3 install-t575-cage-overlay.py ./t575-cage-overlay-aarch64.tar.gz")
    archive = Path(sys.argv[1]).expanduser().resolve(strict=True)
    if archive.name != ARCHIVE_NAME or not archive.is_file():
        fail("Wrong Cage overlay archive")
    if ROOT.is_symlink() or not ROOT.is_dir() or not ROOT.is_mount() and not ROOT.parent.is_mount():
        fail("External T575-Plasma NFS root filesystem is not mounted")
    sha = archive.parent / "SHA256SUMS"
    if not sha.is_file(): fail("Missing SHA256SUMS manifest")
    lines = [line.split() for line in sha.read_text().splitlines() if line.strip()]
    expected = [parts[0] for parts in lines if len(parts) >= 2 and Path(parts[-1]).name == ARCHIVE_NAME]
    if len(expected) != 1 or len(expected[0]) != 64:
        fail("Missing or invalid archive SHA256")
    h = hashlib.sha256()
    with archive.open("rb") as fp:
        while chunk := fp.read(1024 * 1024):
            h.update(chunk)
    if h.hexdigest() != expected[0]:
        fail("Overlay archive SHA256 verification FAILED")

    root_real = ROOT.resolve(strict=True)
    with tarfile.open(archive, "r:gz") as tf:
        members = tf.getmembers()
        seen = set()
        planned = []
        for m in members:
            name = entry_name(m)
            if name in seen: fail(f"Duplicate tar member: {name}")
            seen.add(name)
            if not (m.isdir() or m.isfile() or m.issym() or m.islnk()):
                fail(f"Unsupported special archive member: {name}")
            planned.append((name, m))
        if "usr/bin/cage" not in seen:
            fail("Not a Cage overlay: /usr/bin/cage missing")

        # PRE-FLIGHT all paths for conflicts before writing anything.
        for name, m in planned:
            target = ROOT / name
            parent = target.parent
            while parent != ROOT and not parent.exists():
                parent = parent.parent
            if parent != ROOT:
                actual = parent.resolve(strict=True)
                if not actual.is_relative_to(root_real):
                    fail(f"Path escapes Linux NFS tree via symlink: {name}")
            exists = os.path.lexists(target)
            if not exists:
                continue
            if m.isdir() and target.is_dir() and not target.is_symlink():
                continue
            if m.issym() and target.is_symlink() and os.readlink(target) == m.linkname:
                continue
            if m.isfile() and same_content(target, tf, m):
                continue
            if m.islnk():
                src = ROOT / entry_name(type("T", (), {"name":m.linkname})())
                if src.is_file() and target.is_file() and src.samefile(target):
                    continue
            fail(f"Existing file conflict, no changes made: {target}")

        count = 0
        for name, m in planned:
            if not m.isdir(): continue
            target = ROOT / name
            target.mkdir(mode=0o755, parents=True, exist_ok=True)
        # Do not follow or overwrite symlinks while creating files.
        for name, m in planned:
            target = ROOT / name
            if os.path.lexists(target): continue
            target.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
            if m.isfile():
                stream = tf.extractfile(m)
                if stream is None: fail(f"Cannot read {name}")
                with stream, target.open("xb") as out:
                    while chunk := stream.read(1024 * 1024):
                        out.write(chunk)
                os.chmod(target, m.mode & 0o777)
                count += 1
        for name, m in planned:
            target = ROOT / name
            if os.path.lexists(target): continue
            if m.islnk():
                link_source = ROOT / entry_name(type("T", (), {"name":m.linkname})())
                if not link_source.is_file(): fail(f"Missing hardlink target: {m.linkname}")
                os.link(link_source, target)
                count += 1
        for name, m in planned:
            target = ROOT / name
            if os.path.lexists(target): continue
            if m.issym():
                os.symlink(m.linkname, target)
                count += 1
    cage = ROOT / "usr/bin/cage"
    if not cage.is_file() or not os.access(cage, os.X_OK):
        fail("Cage executable is missing or not executable")
    print(f"PASS: installed {count} new Cage files on Mac external NFS volume")
    print("Tablet BOOT, DTBO, Android userdata and metadata were never accessed.")
    print("Now run: sudo python3 launch-t575-plasma.py ./t575-plasma-launch-aarch64")

if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, tarfile.TarError) as error:
        sys.exit("STOP: " + str(error))
