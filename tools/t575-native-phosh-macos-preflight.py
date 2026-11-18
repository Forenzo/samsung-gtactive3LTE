#!/usr/bin/env python3
"""SM-T575 native Phosh install admission: READ-ONLY Mac preflight.

Checks the LOCAL signed/manifested full disk image, BOOT and fallback images,
and LIVE Linux diagnostic sysfs partition identity using ONLY 'cat'.
No flashing, file extraction, partition writes, discard, reboot or install.
No --apply/--write mode exists. This is not a userdata-erase authorization.
"""
import argparse
import hashlib
from pathlib import Path
import re
import shutil
import socket
import struct
import subprocess
import sys
import uuid
import zlib

EXPECTED_STOCK = "a69a724b75a51821a0baa4ccda424173a003b17de19e2b381bb7d4f30596e372"
EXPECTED_DIAG = "8225061aa97b72f41f27ffc0119d84f1fd22c0d6b009d5e123b811f1796792f7"
BOOT_BYTES = 61_865_984
USERDATA_BYTES = 55_461_281_792
SECTOR = 4096
FIRST_BOOT_RESERVE = (6 << 30) + (400 << 20)
ESP_GUID = uuid.UUID("c12a7328-f81f-11d2-ba4b-00a0c93ec93b")
IMAGE_PREFIX = "samsung-gtactive3-lte_phosh_edge_26111790"
MARKER = b"SM-T575 LTE RESEARCH BOOTCHAIN"


def require(ok, message):
    if not ok:
        raise ValueError(message)
    print("PASS:", message)


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check_boot(path, expected=None, marker=False):
    require(path.is_file() and path.stat().st_size == BOOT_BYTES,
            f"{path.name}: BOOT exact {BOOT_BYTES}-byte size")
    with path.open("rb") as f:
        hdr = f.read(2048)
        f.seek(-64, 2)
        footer = f.read(64)
        f.seek(0)
        found_marker = False
        if marker:
            # Scanner bounded to the single BOOT partition.
            chunk = f.read()
            found_marker = MARKER in chunk
    require(hdr[:8] == b"ANDROID!" and
            struct.unpack_from("<I", hdr, 8 + 8 * 4)[0] == 2 and
            struct.unpack_from("<I", hdr, 8 + 7 * 4)[0] == 2048,
            f"{path.name}: Android BOOT v2, 2048-byte page")
    require(footer[:4] == b"AVBf", f"{path.name}: AVB footer present")
    if expected is not None:
        require(sha256(path) == expected, f"{path.name}: exact known-good SHA-256")
    if marker:
        require(found_marker, f"{path.name}: embedded LTE U-Boot inspection marker")
    return sha256(path) if expected is None else expected


def read_first_decompressed(image, n=1 << 20):
    zstd = shutil.which("zstd")
    require(zstd is not None, "zstd command installed for bounded GPT read")
    p = subprocess.Popen([zstd, "-dcq", str(image)], stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL)
    try:
        data = p.stdout.read(n)
    finally:
        p.kill()
        p.wait(timeout=10)
    require(len(data) == n, "decompressed disk prefix available")
    return data


def gpt(prefix):
    h = prefix[SECTOR:SECTOR + 92]
    require(h[:8] == b"EFI PART", "4 KiB-sector primary GPT header")
    hsz, stored_crc = struct.unpack_from("<II", h, 12)
    require(92 <= hsz <= SECTOR, "plausible GPT header size")
    buf = bytearray(prefix[SECTOR:SECTOR + hsz])
    struct.pack_into("<I", buf, 16, 0)
    require(zlib.crc32(buf) & 0xffffffff == stored_crc, "primary GPT CRC")
    primary, backup, first, last = struct.unpack_from("<QQQQ", h, 24)
    require(primary == 1 and backup > last > first, "primary/backup GPT disk limits")
    array_lba, count, entry_size, array_crc = struct.unpack_from("<QIII", h, 72)
    arr_length = count * entry_size
    require(count <= 256 and entry_size == 128 and
            (array_lba * SECTOR + arr_length) <= len(prefix),
            "partition entry array fits inspected prefix")
    arr = prefix[array_lba * SECTOR:array_lba * SECTOR + arr_length]
    require((zlib.crc32(arr) & 0xffffffff) == array_crc,
            "partition-entry array CRC")
    parts = []
    for i in range(count):
        e = arr[i * entry_size:(i + 1) * entry_size]
        if e[:16] == bytes(16):
            continue
        ptype = uuid.UUID(bytes_le=e[:16])
        start, end = struct.unpack_from("<QQ", e, 32)
        require(first <= start <= end <= last, f"GPT partition {i + 1} lies within usable LBAs")
        parts.append((i + 1, ptype, start, end))
    require(len(parts) == 3 and parts[0][0] == 1 and parts[0][1] == ESP_GUID,
            "exactly three source partitions, first is EFI System Partition")
    require(parts[0][2] * SECTOR == 1048576 and
            (parts[0][3] - parts[0][2] + 1) * SECTOR == 1073741824,
            "EFI partition expected offset and 1 GiB size")
    require(all(parts[i][3] < parts[i + 1][2] for i in range(len(parts) - 1)),
            "no overlapping GPT partitions")
    raw_size = (backup + 1) * SECTOR
    require(raw_size == 6862950400, "expected raw disk size from GPT backup LBA")
    require(raw_size + FIRST_BOOT_RESERVE <= USERDATA_BYTES,
            "Phosh source plus first-boot reserve fits SM-T575 userdata")
    print("INFO: verified projected disk", raw_size, "bytes; userdata headroom",
          USERDATA_BYTES - raw_size - FIRST_BOOT_RESERVE, "bytes")
    return raw_size


def verify_manifest(image):
    require(image.is_file() and image.name == IMAGE_PREFIX + ".raw.zst",
            "exact SM-T575 native Phosh image filename")
    manifest = image.parent / "SHA256SUMS"
    require(manifest.is_file(), "CI SHA256SUMS beside compressed image")
    expect = {}
    for l in manifest.read_text(errors="replace").splitlines():
        m = re.fullmatch(r"([0-9a-f]{64})\s+\*?([^/\\]+)", l.strip())
        if m:
            expect[m.group(2)] = m.group(1)
    require(image.name in expect, "full disk image has CI SHA-256 manifest entry")
    require(sha256(image) == expect[image.name], "local compressed image matches CI SHA-256")


def read_console(interface, host, port, command):
    # A fresh connection for each command; read the banner first.
    with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as s:
        s.settimeout(4.0)
        s.connect((host, port, 0, socket.if_nametoindex(interface)))
        b = bytearray()
        while not b.endswith(b"> ") and len(b) < 12000:
            t = s.recv(4096)
            if not t:
                raise ValueError("Linux diagnostic console closed before prompt")
            b.extend(t)
        s.sendall(("cat " + command + "\n").encode())
        b = bytearray()
        while not b.endswith(b"> ") and len(b) < 128000:
            t = s.recv(4096)
            if not t:
                break
            b.extend(t)
    text = bytes(b).decode("utf-8", "replace").replace("\x00", "")
    # Strip the trailing prompt, preserving all preceding content.
    return text.rsplit("> ", 1)[0].strip()


def live_geometry(args):
    def cat(path):
        answer = read_console(args.interface, args.host, args.port, path)
        require(not answer.startswith("error"), f"read-only console cat {path} responded")
        return answer
    model = cat("/proc/device-tree/model")
    require("SM-T575" in model, f"physical Linux device model is SM-T575 ({model})")
    for n, part_name, size in (("sda12", "boot", BOOT_BYTES),
                               ("sda31", "userdata", USERDATA_BYTES)):
        info = cat(f"/sys/class/block/{n}/uevent").lower()
        require(f"partname={part_name}" in info,
                f"/dev/{n} is explicitly named {part_name} by Linux sysfs")
        sectors = cat(f"/sys/class/block/{n}/size")
        require(sectors.isdigit() and int(sectors) * 512 == size,
                f"/dev/{n} exact measured size {size} bytes")
    mounts = cat("/proc/mounts")
    require("/dev/sda31 " not in mounts and "/dev/sda12 " not in mounts,
            "BOOT and userdata are not mounted")
    print("PASS: live model, partition names/sizes and unmounted state match")
    print("NOTE: passive validation does not verify flash reliability or Android data backup")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    home = Path.home() / "Downloads"
    p.add_argument("--image", type=Path,
                   default=home / "T575-Phosh" / (IMAGE_PREFIX + ".raw.zst"))
    p.add_argument("--bootchain", type=Path,
                   default=home / "T575-BOOT-first-handoff" / "t575-phosh-chain-BOOT-UNTESTED.img")
    p.add_argument("--stock", type=Path,
                   default=home / "SM-T575-Recovery" / "boot-current.img")
    p.add_argument("--diagnostic", type=Path,
                   default=home / "SM-T575-Recovery" / "t575-gpu-BOOT-CANDIDATE.img")
    p.add_argument("--interface", default="en7")
    p.add_argument("--host", default="fe80::57:aff:fe00:1")
    p.add_argument("--port", type=int, default=23)
    p.add_argument("--offline-only", action="store_true", help="skip read-only live identity check")
    args = p.parse_args()
    print("SM-T575 MAC PHOSH INSTALL PREFLIGHT — STRICTLY READ ONLY")
    print("No --apply option exists; cannot write partitions, flash, or reboot.\n")
    try:
        verify_manifest(args.image)
        gpt(read_first_decompressed(args.image))
        print("INFO: verified local chain BOOT sha256",
              check_boot(args.bootchain, marker=True))
        check_boot(args.stock, expected=EXPECTED_STOCK)
        check_boot(args.diagnostic, expected=EXPECTED_DIAG)
        if args.offline_only:
            print("SKIP: physical target identity (offline-only requested)")
        else:
            live_geometry(args)
        print("\nPASS: read-only LTE native image and local recovery admission.")
        print("STILL BLOCKED: destructive installer, vendor firmware,")
        print("              independent U-Boot EFI handoff and full Phosh first boot.")
        print("NO DEVICE WRITES; NO USERDATA ERASE; NO BOOT FLASH.")
    except (OSError, ValueError, struct.error, subprocess.SubprocessError) as e:
        sys.exit("FAIL CLOSED: " + str(e))


if __name__ == "__main__":
    main()
