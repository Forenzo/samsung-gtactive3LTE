#!/usr/bin/env python3
"""Offline admission audit of an SM-T575 first-boot Android BOOT v2 candidate.

For the ORIGINAL, already backed-up rooted SM-T575 T575XXSFEYI1 only.
Checks structure, header provenance, exact LTE loader contents and inherited
Samsung DTB; reads the AVB footer but does not verify its signature.
NO adb, Heimdall, flashing, device access, or candidate rewriting.
"""
import argparse
import hashlib
from pathlib import Path
import struct
import sys

BOOT_SHA = "a69a724b75a51821a0baa4ccda424173a003b17de19e2b381bb7d4f30596e372"
BOOT_BYTES = 61_865_984
PAGE = 2048
MARKER = b"SEANDROIDENFORCE"
AVB_FOOTER_SIZE = 64

def sha(data):
    return hashlib.sha256(data).hexdigest()

def load(path, maxbytes=BOOT_BYTES):
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"missing / symlink path: {path}")
    if not 0 < path.stat().st_size <= maxbytes:
        raise ValueError(f"file size outside limit: {path}")
    return path.read_bytes()

def aligned(n):
    return ((n + PAGE - 1) // PAGE) * PAGE

def boot_sections(blob):
    h = blob[:PAGE]
    if len(h) != PAGE or h[:8] != b"ANDROID!":
        raise ValueError("not an Android BOOT image")
    if struct.unpack_from("<I", h, 36)[0] != PAGE or struct.unpack_from("<I", h, 40)[0] != 2:
        raise ValueError("not the expected v2 / 2048-byte page header")
    if struct.unpack_from("<I", h, 1644)[0] != 1660:
        raise ValueError("unexpected BOOT v2 header length")
    off = PAGE
    parts = {}
    for name, loc in (("kernel", 8), ("ramdisk", 16), ("second", 24),
                      ("recovery_dtbo", 1632), ("dtb", 1648)):
        n = struct.unpack_from("<I", h, loc)[0]
        if off + n > len(blob):
            raise ValueError(f"{name} exceeds image boundary")
        parts[name] = blob[off:off+n]
        off += aligned(n)
    return h, parts, off

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--candidate", type=Path, required=True,
                    help="locally packaged, full-length first-boot BOOT image (read only)")
    ap.add_argument("--loader", type=Path, required=True,
                    help="raw LTE loader to match byte-for-byte to candidate kernel")
    ap.add_argument("--stock", type=Path, default=Path.home() / "Downloads/SM-T575-Recovery/boot-current.img")
    args = ap.parse_args()
    print("SM-T575 first-boot BOOT admission — offline only")
    try:
        original = load(args.stock.expanduser())
        if len(original) != BOOT_BYTES or sha(original) != BOOT_SHA:
            raise ValueError("working rooted Android BOOT backup fingerprint mismatch")
        candidate = load(args.candidate.expanduser())
        loader = load(args.loader.expanduser())
        if len(candidate) != BOOT_BYTES:
            raise ValueError(f"candidate must fill exact BOOT partition ({BOOT_BYTES:,} bytes)")
        if len(loader) < 64 or loader[56:60] != b"ARM\x64":
            raise ValueError("LTE loader missing AArch64 Image header")
        memory_size = struct.unpack_from("<Q", loader, 16)[0]
        if not len(loader) <= memory_size < 256 * 1024 * 1024:
            raise ValueError("AArch64 Image memory footprint invalid")
        stock_h, stock_parts, _ = boot_sections(original)
        new_h, parts, end = boot_sections(candidate)
        if new_h[48:64] != stock_h[48:64]:
            raise ValueError("T575 board identifier mismatch")
        for field, off, size in (("kernel address", 12, 4), ("ramdisk address", 20, 4),
                                 ("tags address", 32, 4), ("dtb address", 1652, 8),
                                 ("OS metadata", 44, 4)):
            if new_h[off:off+size] != stock_h[off:off+size]:
                raise ValueError(f"{field} differs from trusted rooted Android BOOT")
        if parts["kernel"] != loader:
            raise ValueError("candidate kernel is not byte-identical to supplied LTE loader")
        if not parts["ramdisk"]:
            raise ValueError("candidate missing diagnostic ramdisk")
        if parts["ramdisk"] == stock_parts["ramdisk"]:
            raise ValueError("candidate retains rooted Android ramdisk, not a diagnostic ramdisk")
        if parts["dtb"] != stock_parts["dtb"]:
            raise ValueError("embedded Samsung DTB differs from original T575")
        if end + len(MARKER) > BOOT_BYTES - AVB_FOOTER_SIZE:
            raise ValueError("BOOT segments leave no room for Samsung marker and AVB footer")
        if candidate[end:end+len(MARKER)] != MARKER:
            raise ValueError("Samsung marker absent after BOOT sections")
        footer = candidate[-AVB_FOOTER_SIZE:]
        # AVB footer wire format: big-endian magic, 2 versions,
        # original_image_size, vbmeta_offset, vbmeta_size, 28 reserved.
        magic, major, minor, original_size, vbmeta_offset, vbmeta_size, _ = struct.unpack(
            ">4sIIQQQ28s", footer)
        if magic != b"AVBf" or major != 1:
            raise ValueError("missing/unexpected AVB hash footer")
        if (original_size < end + len(MARKER) or original_size > vbmeta_offset or
                vbmeta_size == 0 or vbmeta_offset + vbmeta_size > BOOT_BYTES - AVB_FOOTER_SIZE):
            raise ValueError("invalid AVB footer offsets/sizes")
        print(f"  Candidate full BOOT image: {len(candidate):,} bytes; SHA-256 {sha(candidate)}")
        print(f"  LTE loader: {len(loader):,} bytes; SHA-256 {sha(loader)}; exact match")
        print(f"  RAM load footprint declared by header: {memory_size:,} bytes")
        print(f"  Diagnostic ramdisk: {len(parts['ramdisk']):,} bytes (not rooted stock)")
        print(f"  Embedded original Samsung DTB: {len(parts['dtb']):,} bytes, exact match")
        print(f"  AVB footer found: v{major}.{minor}, vbmeta {vbmeta_size:,} bytes")
        print("  Image layout/provenance: PASS")
        print("  AVB cryptographic validation: NOT PERFORMED")
        print("  Samsung S-Boot acceptance, EL/cache handover, safe restore: NOT VERIFIED")
        print("  RESTORE/BOOT/FLASH GATE: BLOCKED")
        return 0
    except (OSError, ValueError, struct.error) as exc:
        print(f"  Image admission FAIL: {exc}", file=sys.stderr)
        print("  RESTORE/BOOT/FLASH GATE: BLOCKED")
        return 1

if __name__ == "__main__":
    sys.exit(main())
