#!/usr/bin/env python3
"""Stage 20: offline local search for *plausible* SM-T575 recovery material.

Reads directory metadata only; no ADB, network, archive extraction or writes.
Do not interpret a filename or file size as evidence of restorable firmware.
"""
import argparse
import os
from pathlib import Path

BOOT_SIZE = 61_865_984
DTBO_SIZE = 8_388_608
MARKERS = ("t575", "gtactive3lte", "xxsfeyi1")
EXTENSIONS = (".img", ".tar", ".tar.md5", ".zip", ".7z", ".lz4", ".md5")
EXCLUDE = {".git", ".Trash", "node_modules", ".venv", "venv", "__pycache__"}

def classify(filename, size):
    lower = filename.lower()
    if not lower.endswith(EXTENSIONS):
        return None
    if any(x in lower for x in MARKERS):
        return "T575-NAMED CANDIDATE — firmware/build identity unverified"
    if lower in ("boot.img", "boot_a.img", "boot_b.img") and size == BOOT_SIZE:
        return "BOOT-SIZED CANDIDATE — device provenance unverified"
    if lower in ("dtbo.img", "dtbo_a.img", "dtbo_b.img") and size == DTBO_SIZE:
        return "DTBO-SIZED CANDIDATE — device provenance unverified"
    return None

def scan(folder, depth, limit):
    root = folder.expanduser().resolve()
    if not root.is_dir():
        print(f"Missing directory: {folder}")
        return 0
    hits = 0
    for here, dirs, files in os.walk(root, followlinks=False):
        here = Path(here)
        level = len(here.relative_to(root).parts)
        dirs[:] = [d for d in sorted(dirs) if d not in EXCLUDE and
                   not (here / d).is_symlink()] if level < depth else []
        for name in sorted(files):
            candidate = here / name
            try:
                if candidate.is_symlink() or not candidate.is_file():
                    continue
                size = candidate.stat().st_size
            except OSError:
                continue
            category = classify(name, size)
            if category is None:
                continue
            # Show basename and size, not the private full local path.
            print(f"  {name} | {size} bytes | {category}")
            hits += 1
            if hits >= limit:
                print("Hit limit reached: other candidates may exist.")
                return hits
    return hits

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folders", type=Path, nargs="*", help="local folders to scan")
    parser.add_argument("--depth", type=int, default=3)
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    if not 0 <= args.depth <= 8 or not 1 <= args.limit <= 500:
        parser.error("--depth must be 0..8 and --limit 1..500")
    folders = args.folders or [Path.home() / "Downloads", Path.home() / "Documents",
                                Path.home() / "Desktop"]
    total = 0
    print("Stage 20 — locally discover T575-labeled firmware and partition-sized candidates")
    for folder in folders:
        print(f"Scanning: {folder.name}")
        total += scan(folder, args.depth, args.limit - total)
        if total >= args.limit:
            break
    print(f"Candidates: {total}")
    print("A size match or a T575 name is not proof of matching working firmware.")
    print("Recovery: STILL BLOCKED. No ADB, writes, uploads, flashing or archive extraction.")

if __name__ == "__main__":
    main()
