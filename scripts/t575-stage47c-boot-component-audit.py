#!/usr/bin/env python3
"""Stage 47C: offline validation of separate Linux boot components.

The kernel Image, T575 DTB, and diagnostic initramfs are not a Samsung BOOT
image. The T570 uniLoader build/config and the Android v2/S-Boot handover
are NOT validated for LTE. No writes to the tablet, no packaging, no flashing.
"""
import argparse
import gzip
import hashlib
from pathlib import Path
import struct
import sys

TRUSTED_BOOT_SIZE = 61865984
TRUSTED_BOOT_SHA = "a69a724b75a51821a0baa4ccda424173a003b17de19e2b381bb7d4f30596e372"
MAX_IMAGE = 256 * 1024 * 1024
MAX_DTB = 4 * 1024 * 1024
MAX_INITRAMFS = 64 * 1024 * 1024

def file_read(path, limit):
    path = path.expanduser()
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"{path.name} is missing or a symlink")
    size = path.stat().st_size
    if not (0 < size <= limit):
        raise ValueError(f"{path.name} has an invalid size: {size}")
    return path.read_bytes()

def examine(args):
    image = file_read(args.kernel, MAX_IMAGE)
    if len(image) < 64 or image[0x38:0x3c] != b"ARM\x64":
        raise ValueError("not an ARM64 Linux Image (missing magic at 0x38)")
    text_offset, image_size = struct.unpack_from("<QQ", image, 8)
    if image_size and image_size > MAX_IMAGE:
        raise ValueError("kernel header reports unreasonable image_size")
    print(f"  ARM64 Image: PASS ({len(image)} bytes; image_size={image_size}, text_offset={text_offset})")

    dtb = file_read(args.dtb, MAX_DTB)
    if len(dtb) < 40 or dtb[:4] != bytes.fromhex("d00dfeed"):
        raise ValueError("LTE DTB missing flattened-device-tree header")
    total_size = struct.unpack_from(">I", dtb, 4)[0]
    if not (40 <= total_size <= len(dtb)):
        raise ValueError("LTE DTB totalsize outside available bytes")
    if b"samsung,gtactive3lte" not in dtb:
        raise ValueError("LTE DTB missing expected compatible")
    print(f"  T575 DTB: PASS ({total_size} bytes; LTE compatible present)")

    packed = file_read(args.initramfs, MAX_INITRAMFS)
    if packed[:2] != b"\x1f\x8b":
        raise ValueError("initramfs is not a gzip stream")
    try:
        expanded = gzip.decompress(packed)
    except (OSError, EOFError) as exc:
        raise ValueError("could not decompress diagnostic initramfs") from exc
    if not expanded.startswith(b"070701"):
        raise ValueError("diagnostic initramfs is not newc CPIO")
    if b"init\x00" not in expanded:
        raise ValueError("diagnostic initramfs does not appear to include /init")
    print(f"  Diagnostic initramfs: PASS ({len(packed)} compressed bytes)")

    if args.stock_boot:
        stock_path = args.stock_boot.expanduser()
        if stock_path.is_symlink() or not stock_path.is_file():
            raise ValueError("stock BOOT backup unavailable")
        if stock_path.stat().st_size != TRUSTED_BOOT_SIZE:
            raise ValueError("stock BOOT backup size mismatch")
        h = hashlib.sha256()
        with stock_path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        if h.hexdigest() != TRUSTED_BOOT_SHA:
            raise ValueError("stock BOOT backup fingerprint mismatch")
        with stock_path.open("rb") as f:
            header = f.read(2048)
        if header[:8] != b"ANDROID!" or struct.unpack_from("<I", header, 40)[0] != 2:
            raise ValueError("trusted stock BOOT header is not v2")
        print("  Trusted rooted Android BOOT: PASS (hash, partition length, v2)")
    else:
        print("  Trusted rooted Android BOOT: not supplied (CI only)")
    print("  S-Boot: no runtime handover or loader compatibility evidence from this audit")
    print("  Legacy T570 uniLoader: NOT YET PORTED to T575; do not assume it works")
    print("  Display/simpledrm: static DT checks do not prove visible scanout")
    print("  Restore/boot/flash gate: BLOCKED")
    print("  Stage 47C OFFLINE COMPONENT AUDIT: PASS")

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--kernel", type=Path, required=True)
    ap.add_argument("--dtb", type=Path, required=True)
    ap.add_argument("--initramfs", type=Path, required=True)
    ap.add_argument("--stock-boot", type=Path)
    args = ap.parse_args()
    try:
        examine(args)
    except (OSError, ValueError, struct.error) as exc:
        print(f"Stage 47C OFFLINE COMPONENT AUDIT: FAIL: {exc}", file=sys.stderr)
        print("Restore/boot/flash gate: BLOCKED")
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
