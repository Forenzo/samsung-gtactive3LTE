#!/usr/bin/env python3
"""Assemble one SM-T575 experimental NFS BOOT v2 candidate OFFLINE.

No device access, flashing, kexec, or partition writes. Uses the existing
Nov-13-proven BOOT v2 packaging recipe and locally verified rooted BOOT
backup, but accepts ONLY the audited experimental NFS artifact (ZIP).

The output is an *unapproved* review candidate, not installation instructions.
The non-wiping restore / flash gate remains BLOCKED.
"""
import argparse
import gzip
import hashlib
import importlib.util
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parent.parent
ASSEMBLER = ROOT / "scripts/t575-assemble-candidate.py"
AUDIT = ROOT / "first-gui/audit-netroot-artifact.py"
ADMISSION = ROOT / "scripts/t575-first-boot-admission.py"
REVIEW_IMAGE_SHA = "427be40de7401369888e06e92ba57b3fa12965f83970d3b130930261283134f2"
BOOT_PARTITION_BYTES = 61_865_984
REQUIRED_TAR = {
    "uniLoader-linux-gtactive3", "uniLoader-linux", "uniLoader-chain",
    "ramdisk.cpio.gz", "MANIFEST"
}
ARCHIVE = re.compile(r"gtactive3-bootchain_t575-netroot-experimental-[0-9]+[.]tar[.]gz")


def require_regular(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError("Missing regular file or unexpected symlink: " + str(path))
    return path


def sha(data):
    return hashlib.sha256(data).hexdigest()


def verified_components(artifact):
    """First run the existing complete offline ZIP/bootchain integrity audit."""
    subprocess.run([sys.executable, str(AUDIT), str(artifact)], check=True)
    with zipfile.ZipFile(artifact) as z:
        archives = [name for name in z.namelist() if ARCHIVE.fullmatch(name)]
        if len(archives) != 1:
            raise ValueError("Expected one pinned netroot bootchain archive")
        if sha(z.read("standalone-review/Image")) != REVIEW_IMAGE_SHA:
            raise ValueError("Experimental Image SHA differs from previously audited NFS build")
        result = {}
        with z.open(archives[0]) as stream:
            with tarfile.open(fileobj=stream, mode="r|gz") as tf:
                for member in tf:
                    if member.name not in REQUIRED_TAR or member.name in result:
                        raise ValueError("Unexpected/duplicate bootchain member: " + member.name)
                    if not member.isfile() or member.size > 80 * 1024 * 1024:
                        raise ValueError("Oversize or non-file bootchain member")
                    reader = tf.extractfile(member)
                    if reader is None:
                        raise ValueError("Unreadable bootchain member")
                    result[member.name] = reader.read()
        if set(result) != REQUIRED_TAR:
            raise ValueError("Required bootchain members missing")
    manifest = result["MANIFEST"].decode("utf-8")
    for name in REQUIRED_TAR - {"MANIFEST"}:
        hits = re.findall(r"(?m)^([0-9a-f]{64})  " + re.escape(name) + r"$", manifest)
        if len(hits) != 1 or sha(result[name]) != hits[0]:
            raise ValueError("Bootchain manifest mismatch for " + name)
    if "t575-netroot-experimental" not in manifest:
        raise ValueError("Expected experimental NFS build provenance in manifest")
    loader = result["uniLoader-linux-gtactive3"]
    ramdisk = result["ramdisk.cpio.gz"]
    if len(loader) < 64 or loader[56:60] != b"ARM\x64":
        raise ValueError("LTE uniLoader ARM64 Image header missing")
    if len(ramdisk) >= 64 * 1024 * 1024 or ramdisk[:2] != b"\x1f\x8b":
        raise ValueError("Expected compressed diagnostic ramdisk")
    # A small bounded sanity check: a real initramfs should decompress as cpio.
    if not gzip.decompress(ramdisk).startswith(b"070701"):
        raise ValueError("Diagnostic ramdisk has no newc cpio header")
    print("NFS image SHA pinned to verified artifact:", REVIEW_IMAGE_SHA)
    print("LTE loader SHA256:", sha(loader))
    print("Diagnostic initramfs SHA256:", sha(ramdisk))
    return loader, ramdisk


def original_assembler():
    """Reuse the established November-13 BOOT construction; don't change it."""
    spec = importlib.util.spec_from_file_location("t575_original_assembler", ASSEMBLER)
    if spec is None or spec.loader is None:
        raise ValueError("Cannot import established T575 BOOT assembler")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build(args):
    artifact = require_regular(args.artifact.expanduser())
    stock = require_regular(args.stock.expanduser())
    output = args.output.expanduser().absolute()
    if output.exists() or output.is_symlink():
        raise ValueError("Output already exists. Refusing overwrite: " + str(output))
    if output == stock.absolute():
        raise ValueError("Refusing to overwrite rooted Android BOOT backup")
    original = original_assembler()
    layout = original.parse_stock(stock.read_bytes())
    loader, ramdisk = verified_components(artifact)

    tools_dir = Path.home() / ".cache/gtactive3-t575/aosp-android-15.0.0_r1"
    tools = original.obtain_aosp_tools(tools_dir)
    key = Path.home() / ".cache/gtactive3-t575/local-avb-private.pem"
    key.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if key.is_symlink():
        raise ValueError("Experimental AVB key path must not be a symlink")
    if not key.exists():
        print("Generating a local experimental AVB key (NOT Samsung's key).")
        original.run([
            "openssl", "genpkey", "-algorithm", "RSA",
            "-pkeyopt", "rsa_keygen_bits:4096", "-out", str(key)
        ])
        key.chmod(0o600)
    with tempfile.TemporaryDirectory(prefix="t575-netroot-offline-") as tmp:
        folder = Path(tmp)
        kernel = folder / "lte-loader"
        initramfs = folder / "ramdisk.cpio.gz"
        dtb = folder / "original-samsung.dtb"
        candidate = folder / "candidate.boot.img"
        kernel.write_bytes(loader)
        initramfs.write_bytes(ramdisk)
        dtb.write_bytes(layout["dtb"])

        mk = [sys.executable, "-E", "-s", str(tools["mkbootimg.py"])]
        for name in ("base", "kernel_offset", "ramdisk_offset", "tags_offset", "dtb_offset"):
            mk += ["--" + name, hex(layout[name])]
        mk += [
            "--kernel", str(kernel), "--ramdisk", str(initramfs),
            "--dtb", str(dtb), "--header_version", "2", "--pagesize", "2048",
            "--board", layout["board"], "--cmdline", layout["cmdline"],
            "--os_version", layout["version"], "--os_patch_level", layout["patch"],
            "-o", str(candidate)
        ]
        print("Assembling NFS candidate OFFLINE via established v2 recipe")
        original.run(mk)
        with candidate.open("ab") as file:
            file.write(b"SEANDROIDENFORCE")
        original.run([
            sys.executable, "-E", "-s", str(tools["avbtool.py"]),
            "add_hash_footer", "--image", str(candidate),
            "--partition_name", "boot", "--partition_size", str(BOOT_PARTITION_BYTES),
            "--algorithm", "SHA256_RSA4096", "--key", str(key),
            "--rollback_index", "0"
        ])

        # Full partition-length, original DTB, exact LTE loader, and footer
        # are checked by the already-established independent admission audit.
        original.run([
            sys.executable, str(ADMISSION),
            "--candidate", str(candidate), "--loader", str(kernel),
            "--stock", str(stock)
        ])
        if candidate.stat().st_size != BOOT_PARTITION_BYTES:
            raise ValueError("Candidate is not the exact expected BOOT partition length")
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("xb") as dest, candidate.open("rb") as source:
            shutil.copyfileobj(source, dest)

    print("OFFLINE-ONLY candidate:", output)
    print("Candidate SHA256:", original.checksum(output) if hasattr(original, "checksum") else file_sha(output))
    print("No tablet access, BOOT writes, kexec, or flash requested.")
    print("Non-wiping restore unproven. RESTORE/BOOT/FLASH GATE: BLOCKED.")


def file_sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for data in iter(lambda: f.read(1024 * 1024), b""):
            h.update(data)
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--artifact", required=True, type=Path, help="Audited experimental NFS review ZIP")
    p.add_argument("--stock", type=Path,
                   default=Path.home() / "Downloads/SM-T575-Recovery/boot-current.img")
    p.add_argument("--output", required=True, type=Path, help="NEW, offline-only review BOOT image")
    args = p.parse_args()
    try:
        build(args)
    except (OSError, ValueError, subprocess.CalledProcessError,
            tarfile.TarError, zipfile.BadZipFile, EOFError) as e:
        print("Offline candidate assembly failed:", e, file=sys.stderr)
        print("RESTORE/BOOT/FLASH GATE: BLOCKED.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
