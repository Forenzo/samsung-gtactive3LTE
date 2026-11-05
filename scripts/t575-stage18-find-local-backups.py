#!/usr/bin/env python3
"""Stage 18 — locate possible T575 recovery files on the Mac (offline only).

Filename and file-size inventory in explicitly supplied folders, or ~/Downloads.
No ADB, network, partition reads, writes, archive extraction, or file contents.
Matches are candidates, NOT validated backups. Private paths stay on the Mac.
"""
import argparse
import os
from pathlib import Path

BOOT_BYTES = 61_865_984
DTBO_BYTES = 8_388_608
SKIP_DIRS = {".git", ".cache", ".Trash", "node_modules", "venv", ".venv"}
EXTS = (".img", ".tar", ".tar.md5", ".zip", ".7z", ".lz4")
KEYS = ("t575", "gtactive3", "boot", "dtbo", "magisk", "firmware", "ap_", "bl_", "cp_", "csc_")

def match(name):
    lower = name.lower()
    return lower.endswith(EXTS) and any(x in lower for x in KEYS)

def scan(root, depth, maximum):
    found = []
    root = root.expanduser().resolve()
    if not root.is_dir():
        print(f"Skipped missing/non-directory root: {root}")
        return found
    for parent, dirs, files in os.walk(root, followlinks=False):
        p = Path(parent)
        level = len(p.relative_to(root).parts)
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and
                         not (p / d).is_symlink()) if level < depth else []
        for name in sorted(files):
            if not match(name):
                continue
            candidate = p / name
            try:
                if candidate.is_symlink() or not candidate.is_file():
                    continue
                size = candidate.stat().st_size
            except OSError:
                continue
            found.append((str(candidate), size))
            if len(found) >= maximum:
                return found
    return found

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folders", nargs="*", type=Path,
                        help="local folders to inspect (default: ~/Downloads)")
    parser.add_argument("--depth", type=int, default=3,
                        help="max nested directory levels (default: 3)")
    parser.add_argument("--limit", type=int, default=100,
                        help="max displayed candidates (default: 100)")
    args = parser.parse_args()
    if not 0 <= args.depth <= 10 or not 1 <= args.limit <= 1000:
        parser.error("depth must be 0..10 and limit 1..1000")
    roots = args.folders or [Path.home() / "Downloads"]
    print("Stage 18 — offline recovery candidate search (filenames and sizes only)")
    count = 0
    for root in roots:
        print(f"Searching local folder: {root.expanduser()}")
        for name, size in scan(root, args.depth, args.limit - count):
            hint = ("BOOT size match" if size == BOOT_BYTES else
                    "DTBO size match" if size == DTBO_BYTES else
                    "unverified candidate")
            print(f"  {name} | {size} bytes | {hint}")
            count += 1
        if count >= args.limit:
            print("Output limit reached; additional candidates may exist.")
            break
    if not count:
        print("No candidates in the selected folders. Search other local folders manually.")
    print("NOT VERIFIED: provenance, contents, installed Magisk state, restore capability.")
    print("BOOT TEST GATE: BLOCKED; no device operations were performed.")
    print("Do not paste private paths, firmware images, or identifiers into public GitHub.")

if __name__ == "__main__":
    main()
