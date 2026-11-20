#!/usr/bin/env python3
"""SM-T575 explicit destructive image sender for separately armed v4 receiver.

Default invocation performs offline safety validation. --apply is deliberately
required to make any network connection or write to the tablet.
"""
import argparse
import hashlib
import json
import secrets
import socket
import struct
import subprocess
import sys
import zlib
from pathlib import Path

IMAGE_SIZE = 6_862_950_400
TARGET_SIZE = 55_461_281_792
CHUNK = 1_048_576
SECTOR = 4096
PATCH_FILES = ['protective-mbr.bin', 'primary-gpt.bin',
               'backup-entry-array.bin', 'backup-gpt.bin']
PATCH_EXTENTS = [(0,4096),(4096,4096),(55461261312,16384),(55461277696,4096)]


def validate(image, patches):
    if not image.is_file() or image.name != 'samsung-gtactive3-lte_phosh_edge_26111790.raw.zst':
        raise ValueError('unexpected or missing Phosh image')
    manifest = json.loads((patches / 'patch-manifest.json').read_text())
    if (manifest['target_bytes'] != TARGET_SIZE or
            manifest['source_image_bytes'] != IMAGE_SIZE or
            manifest['logical_sector_bytes'] != SECTOR or
            manifest['target_backup_lba'] != 13_540_351):
        raise ValueError('patch manifest does not describe exact SM-T575 release')
    data = []
    for name, (expected_at, expected_size) in zip(PATCH_FILES, PATCH_EXTENTS):
        entry = manifest['patches'][name]
        blob = (patches / name).read_bytes()
        if (entry['offset_bytes'] != expected_at or
                entry['size_bytes'] != expected_size or
                len(blob) != expected_size or
                hashlib.sha256(blob).hexdigest() != entry['sha256']):
            raise ValueError(f'bad GPT patch: {name}')
        data.append((expected_at, blob))
    return data


def recv_exact(sock, count):
    """Read exactly count bytes or fail on disconnect."""
    chunks = bytearray()
    while len(chunks) < count:
        part = sock.recv(count - len(chunks))
        if not part:
            raise RuntimeError(
                f"tablet disconnected during reply "
                f"({len(chunks)}/{count} bytes)"
            )
        chunks.extend(part)
    return bytes(chunks)


def response(sock, data):
    reply = recv_exact(sock, 5)
    expected = zlib.crc32(data) & 0xffffffff
    if reply[0] != ord('K') or struct.unpack('!I', reply[1:])[0] != expected:
        raise RuntimeError('DEVICE READ-BACK MISMATCH: stop; do not reboot')


def packet(sock, operation, offset, data):
    sock.sendall(operation + struct.pack('!QI', offset, len(data)) + data)
    response(sock, data)


def verify_image_sha256(image):
    checksum = Path(str(image) + ".sha256")
    if not checksum.is_file():
        raise ValueError("missing image SHA256 manifest")

    fields = checksum.read_text().strip().split()
    if len(fields) != 2:
        raise ValueError("invalid image SHA256 manifest")

    expected, filename = fields
    if (len(expected) != 64 or
            any(c not in "0123456789abcdef" for c in expected) or
            filename.lstrip("*") not in (str(image), image.name)):
        raise ValueError("unexpected image checksum entry")

    digest = hashlib.sha256()
    with image.open("rb") as f:
        while block := f.read(4 * 1024 * 1024):
            digest.update(block)

    if digest.hexdigest() != expected:
        raise ValueError("IMAGE SHA256 MISMATCH: refusing transfer")

    print("PASS: complete image SHA256 verified", flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--image', type=Path, required=True)
    ap.add_argument('--patches', type=Path, required=True)
    ap.add_argument('--apply', action='store_true', help='actually overwrite SM-T575 userdata')
    ap.add_argument('--token', help='32 lowercase hex characters matching the armed tablet receiver')
    ap.add_argument('--host', default='fe80::57:aff:fe00:1')
    ap.add_argument('--interface', default='en7')
    args = ap.parse_args()
    patch_data = validate(args.image, args.patches)
    verify_image_sha256(args.image)
    print('PASS: exact release and four checksummed GPT relocation patches', flush=True)
    if not args.apply:
        print('DRY RUN PASS: no tablet connection; no userdata writes')
        print('For the destructive transfer, additionally supply --apply --token <32-hex-token>')
        return
    if not args.token or len(args.token) != 32 or any(c not in '0123456789abcdef' for c in args.token):
        raise ValueError('invalid session token')
    confirmation = input('This will DESTROY Android userdata on SM-T575. Type ERASE-SM-T575: ')
    if confirmation != 'ERASE-SM-T575':
        raise ValueError('destructive confirmation rejected')
    scope = socket.if_nametoindex(args.interface)
    proc = subprocess.Popen(['zstd','-dc','--',str(args.image)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=CHUNK)
    written = 0
    try:
        with socket.socket(socket.AF_INET6,socket.SOCK_STREAM) as sock:
            sock.settimeout(180)
            sock.connect((args.host,23457,0,scope))
            sock.sendall(b'T575WR4!' + args.token.encode('ascii') + struct.pack('!Q', IMAGE_SIZE))
            if recv_exact(sock, 2) != b'GO': raise RuntimeError('tablet did not authorize target for writing')
            print('ARMED DEVICE AUTHORIZED. Streaming image...', flush=True)
            while written < IMAGE_SIZE:
                block = proc.stdout.read(min(CHUNK,IMAGE_SIZE-written))
                if not block or len(block)%SECTOR or written+len(block)>IMAGE_SIZE:
                    raise RuntimeError('truncated or unaligned raw image')
                packet(sock,b'D',written,block)
                written += len(block)
                if written % (256*CHUNK) == 0:
                    print(f'Verified: {written:,} / {IMAGE_SIZE:,} bytes', flush=True)
            if proc.stdout.read(1): raise RuntimeError('unexpected trailing decompressed bytes')
            if proc.wait()!=0: raise RuntimeError('zstd decompression failed')
            print('Image payload written and read back; applying relocated GPT...',flush=True)
            for off, blob in patch_data: packet(sock,b'P',off,blob)
            sock.sendall(b'F'+struct.pack('!QI',0,0))
            if recv_exact(sock, 4)!=b'DONE':raise RuntimeError('tablet did not report fsync completion')
        print('PASS: image written, read back per chunk, GPT patched and synced')
        print('NOTE: EFI handoff and Phosh first boot have NOT been validated')
    finally:
        if proc.poll() is None:proc.kill()
        proc.wait()

if __name__ == '__main__':
    try:main()
    except (OSError,ValueError,RuntimeError,KeyError,subprocess.SubprocessError) as e:
        print('STOP:',e,file=sys.stderr)
        raise SystemExit(1)
