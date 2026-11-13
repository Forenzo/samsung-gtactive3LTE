#!/usr/bin/env python3
"""Build an OFFLINE-ONLY SM-T575 Android BOOT v2 diagnostic candidate.

Inputs: the byte-exact rooted BOOT backup and one audited GitHub build archive.
Output: a local image, never sent to the tablet. No adb/Heimdall/flash calls.

The independent t575-first-boot-admission.py check is mandatory before saving.
A PASS is structural, NOT Samsung S-Boot acceptance or authorization to flash.
"""
import argparse
import base64
import hashlib
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tarfile
import tempfile
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent.parent
STOCK_SHA = "a69a724b75a51821a0baa4ccda424173a003b17de19e2b381bb7d4f30596e372"
STOCK_BYTES = 61_865_984
LOADER_SHA = "f3e6c5a78735df48e82173c2abfc9a6aa72056c6c8c9d71043d5997cdeebe17b"
RAMDISK_SHA = "5d21b8cefe195f0cd722a805f1f018cf566610be57ba77f884fa1864b0db4b55"
COMMIT = "ab4afa4834c0e3534aadf8ba08f50764bb9fa554"
TAG = "android-15.0.0_r1"
AOSP = "https://android.googlesource.com/platform"
TOOL_FILES = (
    ("system/tools/mkbootimg", "mkbootimg.py", "37d84b3d162e0bc62e36c1f4e1c63c85ea0caa9f29be023eb2f8efe006ad948c"),
    ("system/tools/mkbootimg", "gki/generate_gki_certificate.py", "6ee0b2e3c3323ae8fccf326bf9a526451eac977005efabf7d129b3063bcfb945"),
    ("external/avb", "avbtool.py", "78a50c8620985709f2e131cf948dcd66ecc43f09ed735e09d75751a7e21e4eb8"),
)

def sha(data):
    return hashlib.sha256(data).hexdigest()

def run(args):
    subprocess.run(args, check=True)

def regular(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"missing regular file (or symlink): {path}")
    return path

def aligned(n, page=2048):
    return ((n + page - 1) // page) * page

def obtain_aosp_tools(base):
    base.mkdir(parents=True, exist_ok=True)
    paths = {}
    for project, relative, digest in TOOL_FILES:
        dest = base / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists() or sha(regular(dest).read_bytes()) != digest:
            url = f"{AOSP}/{project}/+/refs/tags/{TAG}/{relative}?format=TEXT"
            print("Fetching pinned AOSP tool:", relative, flush=True)
            with urlopen(url, timeout=45) as response:
                blob = base64.b64decode(response.read(), validate=True)
            if sha(blob) != digest:
                raise ValueError(f"AOSP source hash mismatch: {relative}")
            dest.write_bytes(blob)
        if sha(regular(dest).read_bytes()) != digest:
            raise ValueError(f"cached AOSP tool hash mismatch: {relative}")
        paths[relative] = dest
    return paths

def parse_stock(data):
    if len(data) != STOCK_BYTES or sha(data) != STOCK_SHA:
        raise ValueError("stock BOOT backup fingerprint or size mismatch")
    if data[:8] != b"ANDROID!":
        raise ValueError("stock BOOT image header missing")
    ks, ka, rs, ra, ss, sa, ta, ps, hv, osv = struct.unpack_from("<10I", data, 8)
    dtbo_size = struct.unpack_from("<I", data, 1632)[0]
    header_size = struct.unpack_from("<I", data, 1644)[0]
    dtb_size, dtb_addr = struct.unpack_from("<IQ", data, 1648)
    if (hv, ps, header_size) != (2, 2048, 1660):
        raise ValueError("stock Android boot header is not v2/2048/1660")
    if not ks or not rs or not dtb_size or ss or dtbo_size:
        raise ValueError("unexpected stock sections; refusing to reconstruct image")
    pos = ps + aligned(ks) + aligned(rs)
    dtb = data[pos:pos + dtb_size]
    if len(dtb) != dtb_size:
        raise ValueError("stock DTB truncated")
    v, patch = osv >> 11, osv & 2047
    version = f"{v >> 14}.{(v >> 7) & 127}.{v & 127}"
    year, month = 2000 + (patch >> 4), patch & 15
    if not 1 <= month <= 12:
        raise ValueError("invalid OS patch month in stock header")
    cmd = (data[64:576] + data[608:1632]).split(b"\0", 1)[0].decode("utf-8")
    board = data[48:64].split(b"\0", 1)[0].decode("ascii")
    base = ka - 0x8000
    if base < 0 or ra < base or ta < base or dtb_addr < base:
        raise ValueError("unsupported stock BOOT load addresses")
    return dict(dtb=dtb, base=base, board=board, cmdline=cmd,
                version=version, patch=f"{year:04d}-{month:02d}",
                kernel_offset=ka-base, ramdisk_offset=ra-base,
                tags_offset=ta-base, dtb_offset=dtb_addr-base)

def read_payload(archive):
    with tarfile.open(regular(archive), "r:gz") as tf:
        names = set(tf.getnames())
        if "uniLoader-chain-gtactive3" in names:
            raise ValueError("LTE chainloader found in diagnostic payload")
        for item in ("MANIFEST", "uniLoader-linux-gtactive3", "ramdisk.cpio.gz"):
            if item not in names:
                raise ValueError(f"payload missing {item}")
        manifest = tf.extractfile("MANIFEST").read().decode("utf-8")
        loader = tf.extractfile("uniLoader-linux-gtactive3").read()
        ramdisk = tf.extractfile("ramdisk.cpio.gz").read()
    if COMMIT not in manifest:
        raise ValueError("payload is not the audited GitHub build")
    if sha(loader) != LOADER_SHA or sha(ramdisk) != RAMDISK_SHA:
        raise ValueError("payload SHA256 mismatch")
    if loader[56:60] != b"ARM\x64":
        raise ValueError("not an ARM64 Image-style LTE loader")
    print("Compiled LTE loader: SHA256 verified")
    print("Diagnostic ramdisk: SHA256 verified")
    return loader, ramdisk

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--payload", required=True, type=Path, help="GitHub diagnostic .tar.gz")
    ap.add_argument("--stock", type=Path,
                    default=Path.home() / "Downloads/SM-T575-Recovery/boot-current.img")
    ap.add_argument("--output", required=True, type=Path, help="new OFFLINE-ONLY .img")
    args = ap.parse_args()
    output = args.output.expanduser().resolve()
    if output.exists():
        raise ValueError(f"output already exists (will not overwrite): {output}")
    stock = regular(args.stock.expanduser())
    if output == stock.resolve():
        raise ValueError("output must not be the Android BOOT backup")
    s = parse_stock(stock.read_bytes())
    loader, ramdisk = read_payload(args.payload.expanduser())
    tools_dir = Path.home() / ".cache/gtactive3-t575/aosp-android-15.0.0_r1"
    tools = obtain_aosp_tools(tools_dir)
    key = Path.home() / ".cache/gtactive3-t575/local-avb-private.pem"
    key.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not key.exists():
        print("Generating a LOCAL experimental AVB key; this is NOT a Samsung key")
        run(["openssl", "genpkey", "-algorithm", "RSA",
             "-pkeyopt", "rsa_keygen_bits:4096", "-out", str(key)])
        key.chmod(0o600)
    with tempfile.TemporaryDirectory(prefix="t575-offline-") as temp:
        d = Path(temp)
        k, r, dtb, candidate = [d / x for x in ("lte-loader", "ramdisk.cpio.gz", "stock.dtb", "boot.img")]
        k.write_bytes(loader)
        r.write_bytes(ramdisk)
        dtb.write_bytes(s["dtb"])
        mk = [sys.executable, "-E", "-s", str(tools["mkbootimg.py"])]
        for name in ("base", "kernel_offset", "ramdisk_offset", "tags_offset", "dtb_offset"):
            mk += ["--" + name, hex(s[name])]
        mk += ["--kernel", str(k), "--ramdisk", str(r), "--dtb", str(dtb),
               "--header_version", "2", "--pagesize", "2048",
               "--board", s["board"], "--cmdline", s["cmdline"],
               "--os_version", s["version"], "--os_patch_level", s["patch"],
               "-o", str(candidate)]
        print("Assembling Android BOOT v2, OFFLINE ONLY", flush=True)
        run(mk)
        with candidate.open("ab") as file:
            file.write(b"SEANDROIDENFORCE")
        run([sys.executable, "-E", "-s", str(tools["avbtool.py"]),
             "add_hash_footer", "--image", str(candidate),
             "--partition_name", "boot", "--partition_size", str(STOCK_BYTES),
             "--algorithm", "SHA256_RSA4096", "--key", str(key),
             "--rollback_index", "0"])
        print("Checking assembled BOOT against original rooted stock...", flush=True)
        run([sys.executable, str(ROOT / "scripts/t575-first-boot-admission.py"),
             "--candidate", str(candidate), "--loader", str(k), "--stock", str(stock)])
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(candidate, output)
    print(f"OFFLINE candidate saved: {output}")
    print("NO S-BOOT ACCEPTANCE PROOF / NO NON-WIPING RESTORE PROOF")
    print("RESTORE/BOOT/FLASH GATE: BLOCKED")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, subprocess.CalledProcessError, tarfile.TarError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        print("RESTORE/BOOT/FLASH GATE: BLOCKED", file=sys.stderr)
        sys.exit(1)
