#!/usr/bin/env python3
"""Audit and stage the previously verified Plasma Mobile tarball on macOS.

Safe-by-default: only creates files beneath an EMPTY target directory.
Regular files are written before any symlinks; symlinks are created last.
No services, NFS exports, disk formatting or device writes.

This is a staging copy only: APFS cannot represent every Linux filesystem
feature. Numeric ownership requires running with sudo after reviewing code.
"""
from collections import Counter
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import sys
import tarfile

EXPECTED_VOLUME = Path("/Volumes/T575-Plasma")
EXPECTED_ARCHIVE = EXPECTED_VOLUME / "plasma-rootfs.tar.gz"
EXPECTED_ROOT = EXPECTED_VOLUME / "rootfs"


def clean(value):
    p = PurePosixPath(value)
    if not value or p.is_absolute() or ".." in p.parts:
        raise ValueError(f"unsafe path: {value!r}")
    s = str(p)
    if s in (".", ""):
        raise ValueError("archive contains root-path entry")
    return s


def main():
    if sys.platform != "darwin":
        sys.exit("This staging script is for macOS only.")
    check_only = len(sys.argv) == 2 and sys.argv[1] == "--check-only"
    if len(sys.argv) > 2 or (len(sys.argv) == 2 and not check_only):
        sys.exit("Usage: stage-plasma-macos.py [--check-only]")
    if not check_only and os.geteuid() != 0:
        sys.exit("Run as root to preserve numeric ownership: sudo python3 ...")
    if not EXPECTED_VOLUME.is_mount():
        sys.exit("T575-Plasma volume is not mounted.")
    if EXPECTED_ARCHIVE.is_symlink() or not EXPECTED_ARCHIVE.is_file():
        sys.exit("Missing or symlinked Plasma archive.")
    if not EXPECTED_ROOT.is_dir() or EXPECTED_ROOT.is_symlink():
        sys.exit("Missing rootfs directory or rootfs is a symlink.")
    if any(EXPECTED_ROOT.iterdir()):
        sys.exit("Destination rootfs is not empty; refusing to overwrite files.")
    with tarfile.open(EXPECTED_ARCHIVE, "r:gz") as tf:
        members = tf.getmembers()
        seen = {}
        symlinks = []
        hardlinks = []
        dirs = []
        files = []
        for m in members:
            name = clean(m.name)
            if name in seen:
                raise ValueError(f"duplicate archive path: {name}")
            seen[name] = m
            if m.isdir():
                dirs.append((name, m))
            elif m.isfile():
                files.append((name, m))
            elif m.issym():
                if not m.linkname:
                    raise ValueError(f"empty symlink target: {name}")
                symlinks.append((name, m))
            elif m.islnk():
                hardlinks.append((name, m))
            else:
                raise ValueError(f"unsupported special entry: {name} ({m.type!r})")

        symlink_names = {n for n, _ in symlinks}
        for name, m in [(n, x) for n, x in dirs + files + symlinks + hardlinks]:
            parts = PurePosixPath(name).parts
            for i in range(1, len(parts)):
                parent = "/".join(parts[:i])
                if parent in symlink_names:
                    raise ValueError(f"path traverses archive symlink: {name} via {parent}")
        for name, m in hardlinks:
            target = clean(m.linkname)
            if target not in seen or not seen[target].isfile():
                raise ValueError(f"hardlink target is not a regular file: {name} => {target}")
        print(f"Archive audited: {len(files)} files, {len(dirs)} directories, "
              f"{len(symlinks)} symlinks, {len(hardlinks)} hardlinks", flush=True)
        if check_only:
            print("CHECK ONLY: no files extracted, no NFS export, no tablet writes.")
            return
        # Avoid writing through any archive-created symlink: links are always last.
        # Temporarily grant directory traversal. Restore directory permissions last.
        for name, m in sorted(dirs, key=lambda v: len(PurePosixPath(v[0]).parts)):
            p = EXPECTED_ROOT / name
            p.mkdir(mode=0o755, parents=True, exist_ok=False)
        for name, m in files:
            p = EXPECTED_ROOT / name
            if not p.parent.is_dir():
                raise ValueError(f"missing parent directory: {name}")
            with tf.extractfile(m) as inp, p.open("xb") as out:
                shutil.copyfileobj(inp, out, length=1024 * 1024)
            os.chmod(p, (m.mode & 0o7777) & ~0o6000)
            os.chown(p, m.uid, m.gid)
        for name, m in hardlinks:
            os.link(EXPECTED_ROOT / clean(m.linkname), EXPECTED_ROOT / name)
        for name, m in symlinks:
            # Absolute Linux symlinks are intentionally kept as strings;
            # never follow them on the macOS host.
            p = EXPECTED_ROOT / name
            os.symlink(m.linkname, p)
            os.lchown(p, m.uid, m.gid)
        for name, m in sorted(dirs, key=lambda v: len(PurePosixPath(v[0]).parts), reverse=True):
            p = EXPECTED_ROOT / name
            os.chown(p, m.uid, m.gid)
            os.chmod(p, (m.mode & 0o7777) & ~0o6000)
        print("STAGING COMPLETE: no NFS export or tablet writes performed.")


if __name__ == "__main__":
    main()
