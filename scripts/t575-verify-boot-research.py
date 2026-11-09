#!/usr/bin/env python3
"""Read-only verification of the SM-T575 unsigned BOOT-format research output.

Checks exact source provenance and every Android BOOT v2 segment against the
verified Magisk-rooted backup and raw LTE uniLoader. Does not create images,
sign, interact with devices, or approve flashing.
"""
import argparse
import hashlib
from pathlib import Path
import struct
import sys

STOCK_SHA = "a69a724b75a51821a0baa4ccda424173a003b17de19e2b381bb7d4f30596e372"
RAW_SHA = "e09febf2978313a62290d89ec4dfe762dee6c1e1ab27a6d0912923e2b14bd92a"
RESEARCH_SHA = "4c6c3ef4b8f1fbca4bc89f3e558e4dfa01b949d823f6f7e8b2d9c3f3ba64d690"
PARTITION_BYTES = 61_865_984
PAGE = 2048
MARKER = b"SEANDROIDENFORCE"

def digest(data):
    return hashlib.sha256(data).hexdigest()

def read(path, expected_max):
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"missing or unsafe file: {path}")
    size = path.stat().st_size
    if size == 0 or size > expected_max:
        raise ValueError(f"unexpected file size: {path.name} ({size})")
    return path.read_bytes()

def align(n):
    return (n + PAGE - 1) // PAGE * PAGE

def sections(data):
    h = data[:PAGE]
    if h[:8] != b"ANDROID!" or len(h) != PAGE:
        raise ValueError("Android BOOT v2 header is missing")
    if struct.unpack_from("<I", h, 36)[0] != PAGE:
        raise ValueError("unexpected boot header page size")
    if struct.unpack_from("<I", h, 40)[0] != 2:
        raise ValueError("unexpected header version")
    if struct.unpack_from("<I", h, 1644)[0] != 1660:
        raise ValueError("unexpected v2 header length")
    sizes = (("kernel", 8), ("ramdisk", 16), ("second", 24),
             ("recovery_dtbo", 1632), ("dtb", 1648))
    pos, result = PAGE, {}
    for name, off in sizes:
        length = struct.unpack_from("<I", h, off)[0]
        if pos + length > len(data):
            raise ValueError(f"{name} extends outside file")
        result[name] = data[pos:pos + length]
        pos += align(length)
    return h, result, pos

def main():
    p = argparse.ArgumentParser(description=__doc__)
    default = Path.home() / "Downloads/SM-T575-Recovery"
    p.add_argument("--stock", type=Path, default=default / "boot-current.img")
    p.add_argument("--loader", type=Path, default=default / "loader-research/t575-uniloader-RAW-NOT-FLASHABLE.bin")
    p.add_argument("--candidate", type=Path, default=default / "t575-linux-boot.research")
    args = p.parse_args()
    try:
        stock = read(args.stock.expanduser(), PARTITION_BYTES)
        loader = read(args.loader.expanduser(), PARTITION_BYTES)
        candidate = read(args.candidate.expanduser(), PARTITION_BYTES)
        if len(stock) != PARTITION_BYTES or digest(stock) != STOCK_SHA:
            raise ValueError("trusted Magisk-rooted Android BOOT has changed")
        if digest(loader) != RAW_SHA:
            raise ValueError("raw uniLoader does not match successful build artifact")
        if digest(candidate) != RESEARCH_SHA:
            raise ValueError("research image differs from recorded SHA-256")
        oldhead, old, _ = sections(stock)
        newhead, new, newend = sections(candidate)
        expectedhead = bytearray(oldhead)
        struct.pack_into("<I", expectedhead, 8, len(loader))
        if newhead != expectedhead:
            raise ValueError("other stock Android BOOT header fields were modified")
        if new["kernel"] != loader:
            raise ValueError("candidate kernel segment differs from built uniLoader")
        for name in ("ramdisk", "second", "recovery_dtbo", "dtb"):
            if new[name] != old[name]:
                raise ValueError(f"stock {name} not preserved byte-for-byte")
        if candidate[newend:] != MARKER:
            raise ValueError("unexpected candidate trailer/signature/padding")
        if candidate[newend - align(len(new["dtb"])) + len(new["dtb"]):newend].strip(b"\x00"):
            raise ValueError("nonzero DTB alignment padding")
        print("SM-T575 BOOT research file verified offline")
        print(f"  Candidate: {len(candidate):,} bytes; SHA-256 {RESEARCH_SHA}")
        print(f"  uniLoader payload: {len(loader):,} bytes; exact binary MATCH")
        print("  Android BOOT v2 header: stock-identical except kernel size")
        print("  Stock rooted ramdisk and Samsung DTB: byte-for-byte MATCH")
        print(f"  BOOT partition headroom: {PARTITION_BYTES-len(candidate):,} bytes")
        print("  Footer/signature: ABSENT; NOT flashable; S-Boot handover untested")
        print("  RESTORE/BOOT/FLASH GATE: BLOCKED")
        return 0
    except (OSError, ValueError, struct.error) as exc:
        print(f"BOOT research verification FAIL: {exc}", file=sys.stderr)
        print("  RESTORE/BOOT/FLASH GATE: BLOCKED")
        return 1

if __name__ == "__main__":
    sys.exit(main())
