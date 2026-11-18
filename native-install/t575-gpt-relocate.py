#!/usr/bin/env python3
"""SM-T575 offline GPT relocation patch generation. No block device access.

Produces four binary patches and a JSON manifest; does NOT alter source image
or write to a tablet. Input: exact vetted 4K-sector zstd compressed raw image.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import zlib

SECTOR = 4096
TARGET_BYTES = 55_461_281_792
SOURCE_BYTES = 6_862_950_400


def fail(message):
    raise ValueError(message)


def read_source_prefix(path):
    proc = subprocess.Popen(['zstd', '-dc', '--', str(path)], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        prefix = proc.stdout.read(SECTOR * 8)
    finally:
        proc.stdout.close()
        proc.kill()
        proc.wait()
    if len(prefix) != SECTOR * 8:
        fail('truncated decompressed prefix')
    return prefix


def crc32(data):
    return zlib.crc32(data) & 0xffffffff


def validate_and_patch(prefix, target_size=TARGET_BYTES, source_size=SOURCE_BYTES):
    if target_size != TARGET_BYTES or source_size != SOURCE_BYTES:
        fail('unexpected size: release permits only exact SM-T575 dimensions')
    if target_size % SECTOR or source_size % SECTOR:
        fail('unaligned disk geometry')
    mbr = bytearray(prefix[:SECTOR])
    if mbr[510:512] != b'\x55\xaa':
        fail('invalid protective MBR signature')
    if mbr[450] != 0xee or struct.unpack_from('<I', mbr, 454)[0] != 1:
        fail('unexpected protective MBR partition type/start')
    header = bytearray(prefix[SECTOR:2*SECTOR])
    if header[:8] != b'EFI PART':
        fail('invalid primary GPT signature')
    size = struct.unpack_from('<I', header, 12)[0]
    if not 92 <= size <= SECTOR:
        fail('invalid GPT header size')
    saved = struct.unpack_from('<I', header, 16)[0]
    struct.pack_into('<I', header, 16, 0)
    if crc32(header[:size]) != saved:
        fail('primary GPT checksum mismatch')
    current, alternate, first, last = struct.unpack_from('<QQQQ', header, 24)
    table_lba = struct.unpack_from('<Q', header, 72)[0]
    count, entry_size, entry_crc = struct.unpack_from('<III', header, 80)
    if current != 1 or alternate + 1 != source_size // SECTOR or table_lba != 2:
        fail('unexpected source GPT positions')
    if count != 128 or entry_size != 128:
        fail('unsupported partition-entry geometry')
    table_size = count * entry_size
    sectors = (table_size + SECTOR - 1) // SECTOR
    table = prefix[2*SECTOR:2*SECTOR + table_size]
    if len(table) != table_size or crc32(table) != entry_crc:
        fail('partition entry checksum mismatch')
    if first < table_lba + sectors or last >= alternate - sectors:
        fail('unexpected source usable region')
    entries = []
    spans = []
    for i in range(count):
        entry = table[i*entry_size:(i+1)*entry_size]
        if entry[:16] == b'\0' * 16:
            continue
        start, end = struct.unpack_from('<QQ', entry, 32)
        if not first <= start <= end <= last:
            fail(f'partition {i+1} outside source usable region')
        spans.append((start, end))
        entries.append({'partition': i+1, 'first_lba': start, 'last_lba': end})
    if len(entries) != 3 or [x['partition'] for x in entries] != [1, 2, 3]:
        fail('expected exactly 3 source partitions')
    if any(a[1] >= b[0] for a, b in zip(sorted(spans), sorted(spans)[1:])):
        fail('overlapping source partitions')
    if table[:16] != bytes.fromhex('28732ac11ff8d211ba4b00a0c93ec93b'):
        fail('first partition is not EFI System Partition')
    target_last = target_size // SECTOR - 1
    backup_table_lba = target_last - sectors
    last_usable = backup_table_lba - 1
    if max(end for _,end in spans) > last_usable:
        fail('partitions overlap relocated backup GPT')
    # Update the protective MBR (GPT-aware firmware should see the whole target).
    struct.pack_into('<I', mbr, 458, min(target_last, 0xffffffff))
    # Primary GPT header
    struct.pack_into('<Q', header, 32, target_last)
    struct.pack_into('<Q', header, 48, last_usable)
    struct.pack_into('<I', header, 16, crc32(header[:size]))
    primary = bytes(header)
    # Backup GPT header: same GUID and partition CRC, but own and alternate
    # LBAs and partition-entry-array location must be reversed.
    backup = bytearray(primary)
    struct.pack_into('<Q', backup, 24, target_last)
    struct.pack_into('<Q', backup, 32, 1)
    struct.pack_into('<Q', backup, 72, backup_table_lba)
    struct.pack_into('<I', backup, 16, 0)
    struct.pack_into('<I', backup, 16, crc32(backup[:size]))
    patches = {
        'protective-mbr.bin': (0, bytes(mbr)),
        'primary-gpt.bin': (SECTOR, primary),
        'backup-entry-array.bin': (backup_table_lba * SECTOR, table),
        'backup-gpt.bin': (target_last * SECTOR, bytes(backup)),
    }
    for name, (offset, payload) in patches.items():
        if offset % SECTOR or len(payload) % SECTOR or offset + len(payload) > target_size:
            fail(f'invalid patch extent for {name}')
    return patches, {'target_bytes': target_size, 'source_image_bytes': source_size,
        'logical_sector_bytes': SECTOR, 'source_backup_lba': alternate,
        'target_backup_lba': target_last, 'target_backup_table_lba': backup_table_lba,
        'target_last_usable_lba': last_usable, 'partitions': entries,
        'patches': {k: {'offset_bytes': v[0], 'size_bytes': len(v[1]),
                         'sha256': hashlib.sha256(v[1]).hexdigest()} for k,v in patches.items()},
        'disk_writes_performed': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image', type=Path, help='vetted SM-T575 .raw.zst')
    parser.add_argument('--output', type=Path, required=True, help='new directory for patches')
    args = parser.parse_args()
    if args.output.exists():
        fail('output already exists: will not overwrite existing files')
    if not args.image.is_file() or not args.image.name.endswith('.raw.zst'):
        fail('source image missing or not .raw.zst')
    patches, manifest = validate_and_patch(read_source_prefix(args.image))
    args.output.mkdir(parents=True)
    for name, (_, payload) in patches.items():
        (args.output / name).write_bytes(payload)
    (args.output / 'patch-manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps(manifest, indent=2))
    print('PASS: offline GPT patch generation; NO TABLET WRITES')

if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print('BLOCKED:', exc, file=sys.stderr)
        raise SystemExit(1)
