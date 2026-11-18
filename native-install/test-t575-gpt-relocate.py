#!/usr/bin/env python3
"""Unit checks for source GPT validation, backup header relocation and CRCs."""
import importlib.util
import struct
import unittest
import zlib
from pathlib import Path

src = Path(__file__).with_name('t575-gpt-relocate.py')
spec = importlib.util.spec_from_file_location('gpt', src)
gpt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gpt)

class GPTTests(unittest.TestCase):
    def make_prefix(self):
        sec = gpt.SECTOR
        prefix = bytearray(sec*8)
        prefix[510:512] = b'\x55\xaa'
        prefix[450] = 0xee
        struct.pack_into('<I', prefix, 454, 1)
        struct.pack_into('<I', prefix, 458, gpt.SOURCE_BYTES // sec - 1)
        table = bytearray(128*128)
        # EFI System Partition GUID in little-endian GPT on-disk encoding
        table[:16] = bytes.fromhex('28732ac11ff8d211ba4b00a0c93ec93b')
        struct.pack_into('<QQ', table, 32, 256, 262399)
        for i, lo, hi in [(1,262400,364799),(2,364800,1675519)]:
            off=i*128
            table[off:off+16]=bytes([i+1])*16
            struct.pack_into('<QQ', table, off+32, lo, hi)
        prefix[sec*2:sec*2+len(table)] = table
        header = bytearray(sec)
        header[:8] = b'EFI PART'
        struct.pack_into('<I', header, 8, 0x10000)
        struct.pack_into('<I', header, 12, 92)
        struct.pack_into('<QQQQ', header, 24, 1, gpt.SOURCE_BYTES//sec-1, 6, gpt.SOURCE_BYTES//sec-6)
        struct.pack_into('<Q',header,72,2)
        struct.pack_into('<III',header,80,128,128,zlib.crc32(table)&0xffffffff)
        struct.pack_into('<I',header,16,zlib.crc32(header[:92])&0xffffffff)
        prefix[sec:sec*2] = header
        return prefix
    def test_valid_patch(self):
        patches, manifest=gpt.validate_and_patch(self.make_prefix())
        self.assertEqual(len(patches),4)
        self.assertFalse(manifest['disk_writes_performed'])
        end=gpt.TARGET_BYTES//gpt.SECTOR-1
        self.assertEqual(manifest['target_backup_lba'],end)
        for name in ['primary-gpt.bin','backup-gpt.bin']:
            h=bytearray(patches[name][1]); stored=struct.unpack_from('<I',h,16)[0]
            struct.pack_into('<I',h,16,0)
            self.assertEqual(stored,zlib.crc32(h[:92])&0xffffffff)
        self.assertEqual(struct.unpack_from('<Q',patches['backup-gpt.bin'][1],24)[0],end)
        self.assertEqual(struct.unpack_from('<Q',patches['primary-gpt.bin'][1],32)[0],end)
    def test_bad_gpt_crc_rejected(self):
        data=self.make_prefix()
        data[gpt.SECTOR+42]^=1
        with self.assertRaises(ValueError): gpt.validate_and_patch(data)
    def test_bad_partition_table_crc_rejected(self):
        data=self.make_prefix()
        data[gpt.SECTOR*2+60]^=1
        with self.assertRaises(ValueError): gpt.validate_and_patch(data)
    def test_wrong_target_rejected(self):
        with self.assertRaises(ValueError):
            gpt.validate_and_patch(self.make_prefix(),target_size=32*1024*1024)
    def test_unexpected_mbr_rejected(self):
        data=self.make_prefix(); data[450]=0x83
        with self.assertRaises(ValueError): gpt.validate_and_patch(data)

if __name__=='__main__': unittest.main()
