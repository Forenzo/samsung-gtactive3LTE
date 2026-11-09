#!/usr/bin/env python3
"""SM-T575 experimental Samsung Android BOOT v2 image layout builder (OFFLINE).

Uses the *exact* verified, Magisk-rooted SM-T575 BOOT as a metadata and stock
DTB/ramdisk source. Replaces only the kernel payload with the independently
built LTE uniLoader, using the backup's REAL board string/addresses/version.

This creates an UNSIGNED RESEARCH IMAGE, not a flashable or boot-proven image.
It does NOT preserve or synthesize Samsung signatures, AVB footers or trust.
It has no ADB, Heimdall, USB, reset or partition-writing capability.
Never use the SM-T570 boot packager/installer for this LTE variant.
"""
import argparse
import hashlib
from pathlib import Path
import struct
import sys

BOOT_SHA = "a69a724b75a51821a0baa4ccda424173a003b17de19e2b381bb7d4f30596e372"
BOOT_PARTITION = 61_865_984
PAGE = 2048
HEADER_SIZE = 1660
HEADER_VERSION = 2
SEANDROID = b"SEANDROIDENFORCE"
# Do not impose an arbitrary 50 MiB kernel-payload limit: uniLoader embeds
# the complete Linux Image, DTB and initramfs. The computed BOOT v2 layout
# below enforces the actual partition size instead.

def checksum(data):
    return hashlib.sha256(data).hexdigest()

def align(n):
    return (n + PAGE - 1) // PAGE * PAGE

def layout(h):
    kernel, ramdisk, second = (struct.unpack_from("<I", h, i)[0] for i in (8, 16, 24))
    dtbo = struct.unpack_from("<I", h, 1632)[0]
    dtb = struct.unpack_from("<I", h, 1648)[0]
    result = {}
    pos = PAGE
    for name, size in (("kernel", kernel), ("ramdisk", ramdisk),
                       ("second", second), ("recovery_dtbo", dtbo), ("dtb", dtb)):
        result[name] = (pos, size)
        pos += align(size)
    return result, pos

def assemble(args):
    source = args.boot.expanduser()
    loader = args.loader.expanduser()
    for path in (source, loader):
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"missing regular file: {path}")
    if source.stat().st_size != BOOT_PARTITION:
        raise ValueError("trusted rooted Android BOOT partition size mismatch")
    # Hash locally; do not use files based only on their filename.
    original = source.read_bytes()
    if checksum(original) != BOOT_SHA:
        raise ValueError("rooted BOOT backup differs from verified fingerprint")
    h = bytearray(original[:PAGE])
    if (h[:8] != b"ANDROID!" or
        struct.unpack_from("<I", h, 36)[0] != PAGE or
        struct.unpack_from("<I", h, 40)[0] != HEADER_VERSION or
        struct.unpack_from("<I", h, 1644)[0] != HEADER_SIZE):
        raise ValueError("unexpected Android BOOT header")
    before, old_end = layout(h)
    if old_end > len(original):
        raise ValueError("original segment sizes exceed trusted BOOT partition")
    loader_size = loader.stat().st_size
    if not 0 < loader_size < BOOT_PARTITION:
        raise ValueError(f"raw LTE loader size {loader_size:,} exceeds BOOT partition bounds")
    raw_loader = loader.read_bytes()
    # Samsung compatibility still needs runtime proof, but a raw AArch64
    # Image kernel payload must carry the standard magic at offset 0x38.
    if len(raw_loader) < 64 or raw_loader[0x38:0x3c] != b"ARM\\x64":
        raise ValueError("LTE uniLoader lacks ARM64 Image header; old research artifact is obsolete")
    declared_size = struct.unpack_from("<Q", raw_loader, 0x10)[0]
    if not 0 < declared_size <= len(raw_loader):
        raise ValueError("LTE loader ARM64 Image declared size invalid")
    if raw_loader[:8] == b"ANDROID!":
        raise ValueError("loader already contains an Android BOOT image header")
    if b"T575-LINK-TEST-NOT-BOOTABLE-" in raw_loader[:4096]:
        raise ValueError("loader still contains placeholder blobs")
    # A real linker output may contain the Linux ARM64 magic within its body;
    # this alone does not prove safe launch on SM-T575.
    # Preserve the exact stock header fields, changing ONLY kernel_size.
    struct.pack_into("<I", h, 8, loader_size)
    after, new_end = layout(h)
    if new_end + len(SEANDROID) > BOOT_PARTITION:
        raise ValueError(f"candidate layout needs {new_end + len(SEANDROID):,} bytes; "
                         f"BOOT partition has only {BOOT_PARTITION:,} bytes")
    print("SM-T575 unsigned research image — offline only")
    print(f"  Verified rooted BOOT SHA-256: {BOOT_SHA}")
    print(f"  Board identifier: {h[48:64].split(bytes([0]),1)[0]!r}")
    print(f"  Old Android kernel: {before['kernel'][1]:,} bytes")
    print(f"  Replacement LTE loader: {loader_size:,} bytes ({checksum(raw_loader)})")
    print(f"  Original ramdisk: {before['ramdisk'][1]:,} bytes")
    print(f"  Original Samsung DTB: {before['dtb'][1]:,} bytes")
    print(f"  Candidate size with Samsung marker, before any footer: {new_end+len(SEANDROID):,}")
    print(f"  BOOT partition maximum: {BOOT_PARTITION:,}")
    print("  AVB signing: NONE. Stock signature/footer: NOT REUSED.")
    print("  Samsung S-Boot acceptance: UNKNOWN.")
    print("  Rooted Android ramdisk retained for structural study ONLY.")
    if args.output is not None:
        dest = args.output.expanduser()
        if dest.suffix != ".research":
            raise ValueError("output filename MUST end in .research (deliberately not .img)")
        if dest.exists() or dest.is_symlink():
            raise ValueError("refusing to overwrite existing candidate")
        # Explicitly require an action flag so the default is read-only.
        if not args.emit_unsigned:
            raise ValueError("--output additionally requires --emit-unsigned")
        payload = bytearray(h)
        for name in ("kernel", "ramdisk", "second", "recovery_dtbo", "dtb"):
            piece = raw_loader if name == "kernel" else original[
                before[name][0]:before[name][0] + before[name][1]]
            if len(piece) != after[name][1]:
                raise ValueError(f"{name} segment length mismatch")
            payload.extend(piece)
            payload.extend(bytes(align(len(piece))-len(piece)))
        payload.extend(SEANDROID)
        if len(payload) != new_end + len(SEANDROID):
            raise ValueError("constructed section offsets do not match header")
        # Do not copy AVB footer or pad to BOOT partition size; this is
        # purposefully incomplete and NOT SUITABLE for flashing.
        with dest.open("xb") as f:
            f.write(payload)
        print(f"  Wrote UNSIGNED NON-FLASHABLE RESEARCH FILE: {dest}")
        print(f"  Research file SHA-256: {checksum(payload)}")
    else:
        print("  Dry run only; no candidate file written.")
    print("  No BOOT/DTBO writes. RESTORE/BOOT/FLASH GATE: BLOCKED.")
    return 0

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--boot", type=Path, default=Path.home() /
                   "Downloads/SM-T575-Recovery/boot-current.img")
    p.add_argument("--loader", type=Path, required=True,
                   help="raw uniLoader from verified CI artifact; NOT an Android image")
    p.add_argument("--output", type=Path, help="optional .research file, NOT flashable")
    p.add_argument("--emit-unsigned", action="store_true",
                   help="explicitly allow incomplete unsigned research output")
    a = p.parse_args()
    if a.emit_unsigned and not a.output:
        p.error("--emit-unsigned requires --output")
    try:
        return assemble(a)
    except (OSError, ValueError, struct.error) as exc:
        print(f"OFFLINE BOOT research FAIL: {exc}", file=sys.stderr)
        print("RESTORE/BOOT/FLASH GATE: BLOCKED")
        return 1

if __name__ == "__main__":
    sys.exit(main())
