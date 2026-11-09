#!/usr/bin/env python3
"""SM-T575 local Android BOOT v2 metadata audit (read-only).

Examines the *user's* verified rooted Android BOOT partition image. Prints
exact header fields and embedded Samsung DTB fingerprint for later offline
image packaging. DOES NOT extract, modify, sign, generate or flash anything.
No Samsung firmware is committed to GitHub.
"""
import argparse
import hashlib
from pathlib import Path
import struct
import sys

EXPECTED_SHA = "a69a724b75a51821a0baa4ccda424173a003b17de19e2b381bb7d4f30596e372"
EXPECTED_BYTES = 61865984

def sha256(path, offset=0, size=None):
    h = hashlib.sha256()
    with path.open("rb") as f:
        f.seek(offset)
        remain = size
        while remain is None or remain > 0:
            block = f.read(1024 * 1024 if remain is None else min(remain, 1024 * 1024))
            if not block:
                break
            h.update(block)
            if remain is not None:
                remain -= len(block)
    if remain not in (None, 0):
        raise ValueError("image segment unexpectedly truncated")
    return h.hexdigest()

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--boot", type=Path,
                   default=Path.home() / "Downloads/SM-T575-Recovery/boot-current.img")
    args = p.parse_args()
    path = args.boot.expanduser()
    try:
        if path.is_symlink() or not path.is_file():
            raise ValueError("missing regular rooted Android BOOT backup")
        if path.stat().st_size != EXPECTED_BYTES or sha256(path) != EXPECTED_SHA:
            raise ValueError("backup length/SHA256 differs from trusted SM-T575 recovery image")
        with path.open("rb") as f:
            h = f.read(2048)
        if len(h) != 2048 or h[:8] != b"ANDROID!":
            raise ValueError("Android BOOT magic or header absent")
        # AOSP boot v2: kernel_size/address, ramdisk_size/address,
        # second_size/address, tags_addr, page_size, header_version, os_version.
        vals = struct.unpack_from("<10I", h, 8)
        ks, ka, rs, ra, ss, sa, ta, page, version, os = vals
        recovery_dtbo_size = struct.unpack_from("<I", h, 1632)[0]
        recovery_dtbo_off = struct.unpack_from("<Q", h, 1636)[0]
        header_size = struct.unpack_from("<I", h, 1644)[0]
        dtb_size, dtb_addr = struct.unpack_from("<IQ", h, 1648)
        if page != 2048 or version != 2 or header_size != 1660:
            raise ValueError("unexpected T575 boot-image v2 layout")
        if not ks or not dtb_size:
            raise ValueError("backup has no kernel or Samsung DTB")
        def up(x): return (x + page - 1) // page * page
        offset = page
        sections = {}
        for name, size in (("kernel", ks), ("ramdisk", rs), ("second", ss),
                           ("recovery_dtbo", recovery_dtbo_size), ("dtb", dtb_size)):
            if offset + size > EXPECTED_BYTES:
                raise ValueError(f"{name} extends past BOOT partition")
            sections[name] = (offset, size)
            offset += up(size)
        if recovery_dtbo_size and recovery_dtbo_off != sections["recovery_dtbo"][0]:
            raise ValueError("recovery DTBO offset disagrees with computed layout")
        board = h[48:64].split(b"\0", 1)[0].decode("ascii", "replace")
        cmdline = h[64:576].split(b"\0", 1)[0].decode("ascii", "replace")
        print("SM-T575 original ROOTED Android BOOT — verified read-only")
        print(f"  Trusted whole-partition SHA-256: {EXPECTED_SHA}")
        print(f"  Page size / header version / header size: {page} / {version} / {header_size}")
        print(f"  Board: {board!r}  Kernel address: {ka:#x}")
        print(f"  Ramdisk address: {ra:#x}  Tags address: {ta:#x}")
        print(f"  DTB address: {dtb_addr:#x}  Recovery DTBO bytes: {recovery_dtbo_size}")
        print(f"  OS version packed field: {os:#x}")
        print(f"  Command line (first field): {cmdline!r}")
        for name, (start, length) in sections.items():
            print(f"  {name}: offset {start}, size {length}")
        dstart, dsize = sections["dtb"]
        print(f"  Private embedded Samsung DTB SHA-256: {sha256(path,dstart,dsize)}")
        print("  This backup is MAGISK-ROOTED Android BOOT, not separately extracted factory BOOT.")
        print("  Android BOOT packaging requirements: reported, not implemented here.")
        print("  S-Boot runtime / AVB acceptance / non-wiping restore: NOT verified.")
        print("  RESTORE/BOOT/FLASH GATE: BLOCKED")
        return 0
    except (OSError, ValueError, struct.error) as e:
        print(f"BOOT metadata audit FAIL: {e}", file=sys.stderr)
        print("RESTORE/BOOT/FLASH GATE: BLOCKED")
        return 1

if __name__ == "__main__":
    sys.exit(main())
