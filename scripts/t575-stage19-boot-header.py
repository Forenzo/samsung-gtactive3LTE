#!/usr/bin/env python3
"""Stage 19: offline, read-only Android boot image header checks.

Only reads the first 4096 bytes of explicitly provided files. No ADB,
device access, file modification, firmware unpacking or flashing.
A valid header does not prove T575 provenance or restore safety.
"""
import argparse
import struct
from pathlib import Path

PARTITION_SIZE = 61_865_984
MAGIC = b"ANDROID!"

def u32(buf, offset):
    return struct.unpack_from("<I", buf, offset)[0]

def inspect(path):
    p = Path(path).expanduser()
    print(f"Candidate: {p.name}")
    if p.is_symlink() or not p.is_file():
        print("  UNAVAILABLE: not a regular file or is a symlink")
        return
    size = p.stat().st_size
    print(f"  file bytes: {size}; T575 BOOT partition bytes: {PARTITION_SIZE}")
    print(f"  exact size match: {'yes' if size == PARTITION_SIZE else 'NO'}")
    with p.open("rb") as f:
        header = f.read(4096)
    if len(header) < 48:
        print("  INVALID: too short for a boot header")
        return
    if header[:8] != MAGIC:
        print("  no Android boot-image magic at offset zero")
        print("  File might be compressed, packaged, or not a raw boot image.")
        return
    # Android boot header v0/v1/v2 layout: page_size at offset 36,
    # header_version at offset 40. v3+ layout differs and MUST NOT be
    # interpreted with the old offsets.
    kernel_size = u32(header, 8)
    ramdisk_size = u32(header, 16)
    word36 = u32(header, 36)
    word40 = u32(header, 40)
    print("  Android boot magic: present")
    print(f"  kernel bytes (header): {kernel_size}")
    print(f"  ramdisk bytes (header): {ramdisk_size}")
    if word36 in (2048, 4096, 8192, 16384) and word40 in (0, 1, 2):
        page_size, version = word36, word40
        print(f"  recognized legacy header: version {version}, page_size {page_size}")
        if version >= 1:
            print(f"  recovery_dtbo_size (header): {u32(header, 1632)}")
        if version == 2:
            print(f"  dtb_size (header): {u32(header, 1648)}")
        print("  T575 stock expected header: v2, page_size 2048")
        print(f"  format agreement: {'yes' if (version, page_size) == (2, 2048) else 'NO'}")
    elif word40 in (3, 4):
        print("  possible newer-format image; refusing legacy field interpretation")
    else:
        print("  header layout unrecognized; use a trusted Android boot parser")
    print("  Provenance, Magisk state and restoration: NOT VERIFIED")
    
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("images", nargs="+", help="local candidate boot images")
    args = parser.parse_args()
    for img in args.images:
        inspect(img)
    print("BOOT SAFETY GATE: BLOCKED. Never flash based solely on these checks.")

if __name__ == "__main__":
    main()
