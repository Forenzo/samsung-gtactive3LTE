#!/usr/bin/env python3
"""Offline, read-only audit of a downloaded T575 experimental netroot artifact.

No extraction, mounting, kexec, flashing, network requests, or tablet changes.
This verifies internal hashes, archive structure, and an ARM64 Image header.
It does NOT establish bootability, device compatibility or recovery safety.
"""
import argparse
import hashlib
from pathlib import Path
import re
import sys
import tarfile
import zipfile

IMAGE = "standalone-review/Image"
IMAGE_SUMS = "standalone-review/SHA256SUMS"
CONFIG = "t575-netroot-config-audit.txt"
REVIEW = "standalone-review/REVIEW-ONLY.txt"
ARCHIVE_RE = re.compile(r"gtactive3-bootchain_t575-netroot-experimental-[0-9]+[.]tar[.]gz")
# Bootchain builds both device variants from one Linux Image:
# the default Wi-Fi board has unsuffixed chain/linux loaders, while LTE
# has ONLY its separate linux-gtactive3 loader (never chain-gtactive3).
EXPECTED_TAR = {
    "uniLoader-chain",
    "uniLoader-linux",
    "uniLoader-linux-gtactive3",
    "ramdisk.cpio.gz",
    "MANIFEST",
}
REQUIRED = ("CONFIG_NFS_FS=y", "CONFIG_NFS_V3=y", "CONFIG_SUNRPC=y",
            "CONFIG_LOCKD=y", "CONFIG_USB_CONFIGFS_NCM=y")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def checked_member(z, name, maximum):
    info = z.getinfo(name)
    if info.file_size > maximum:
        raise ValueError(f"ZIP entry too large: {name}")
    return z.read(name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact_zip", type=Path)
    args = parser.parse_args()
    path = args.artifact_zip.expanduser()
    if not path.is_file():
        raise ValueError(f"Artifact missing: {path}")
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Duplicate ZIP members")
        archives = [n for n in names if ARCHIVE_RE.fullmatch(n)]
        if len(archives) != 1:
            raise ValueError("Expected exactly one experimental bootchain archive")
        if any(n not in {IMAGE, IMAGE_SUMS, CONFIG, REVIEW, archives[0]} for n in names):
            raise ValueError("Unexpected ZIP member")
        if not {IMAGE, IMAGE_SUMS, CONFIG, REVIEW}.issubset(set(names)):
            raise ValueError("Expected review/config/Image files missing")
        image = checked_member(z, IMAGE, 128 * 1024 * 1024)
        if len(image) < 4 * 1024 * 1024 or image[56:60] != b"ARMd":
            raise ValueError("Not a recognized ARM64 Image header")
        lines = checked_member(z, IMAGE_SUMS, 4096).decode("ascii").splitlines()
        if len(lines) != 1 or lines[0].split() != [sha(image), "Image"]:
            raise ValueError("ARM64 Image SHA256 manifest mismatch")
        print(f"PASS: ARM64 Image header, {len(image):,} bytes, SHA256 {sha(image)}")
        config = checked_member(z, CONFIG, 16384).decode("utf-8").splitlines()
        for key in REQUIRED:
            if key not in config:
                raise ValueError(f"Missing audited kernel setting: {key}")
        print("PASS: NFSv3/SUNRPC/LOCKD and USB NCM build audit")
        review = checked_member(z, REVIEW, 16384).decode("utf-8")
        for key in ("CONFIG_NET_HANDSHAKE=y", "CONFIG_NFS_FS=y", "CONFIG_NFS_V3=y"):
            if key not in review:
                raise ValueError(f"Missing explicit experimental kernel setting: {key}")
        print("PASS: built-in NET_HANDSHAKE recorded in review notes")
        with z.open(archives[0]) as package:
            checksums = {}
            manifest = None
            found = set()
            with tarfile.open(fileobj=package, mode="r|gz") as t:
                for member in t:
                    if member.name not in EXPECTED_TAR or member.name in found:
                        raise ValueError(f"Unexpected or duplicate bootchain member: {member.name}")
                    if not member.isfile() or member.size > 100 * 1024 * 1024:
                        raise ValueError(f"Unexpected bootchain object: {member.name}")
                    stream = t.extractfile(member)
                    if stream is None:
                        raise ValueError(f"Unreadable bootchain member: {member.name}")
                    digest = hashlib.sha256()
                    content = bytearray() if member.name == "MANIFEST" else None
                    while True:
                        part = stream.read(1024 * 1024)
                        if not part:
                            break
                        digest.update(part)
                        if content is not None:
                            if len(content) + len(part) > 16384:
                                raise ValueError("Oversized manifest")
                            content.extend(part)
                    checksums[member.name] = digest.hexdigest()
                    if content is not None:
                        manifest = bytes(content).decode("utf-8")
                    found.add(member.name)
            if found != EXPECTED_TAR or manifest is None:
                raise ValueError(f"Bootchain members incomplete: {found}")
            for name in sorted(EXPECTED_TAR - {"MANIFEST"}):
                matches = re.findall(r"(?m)^([0-9a-fA-F]{64})  " + re.escape(name) + r"$", manifest)
                if len(matches) != 1 or matches[0].lower() != checksums[name]:
                    raise ValueError(f"Bootchain manifest SHA256 mismatch: {name}")
            if not re.search(r"(?m)^variants:.*gtactive3=", manifest):
                raise ValueError("LTE variant not recorded in bootchain manifest")
            if "contains no Samsung files:" not in manifest:
                raise ValueError("Expected provenance statement missing from manifest")
            print("PASS: Wi-Fi chain/Linux + separate LTE Linux loader; all payload hashes verified")
            print("PASS: no LTE chainloader in bootchain package")
        print("\nOFFLINE ARTIFACT AUDIT: PASS")
        print("NOT a boot or recovery test. No files extracted and no tablet changes.")
        print("DO NOT FLASH OR KEXEC this artifact.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, zipfile.BadZipFile, tarfile.TarError,
            UnicodeError) as exc:
        sys.exit(f"ERROR: {exc}")
