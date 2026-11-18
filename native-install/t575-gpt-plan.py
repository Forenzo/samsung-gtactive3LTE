#!/usr/bin/env python3
"""Offline read-only inspection/planning for an SM-T575 userdata-contained GPT image.

Does not modify the source, partitions, or the device. Computes the backup GPT
placement on /dev/sda31 and validates the primary GPT CRCs and source layout.
"""
import argparse, hashlib, json, pathlib, struct, subprocess, sys, zlib
SECTOR=4096
TARGET=55461281792
IMAGE=6862950400

def read_prefix(path):
    p=subprocess.Popen(['zstd','-dc','--',str(path)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    try: buf=p.stdout.read(256*1024)
    finally:
        p.stdout.close(); p.kill(); p.wait()
    return buf

def file_sha256(path):
    dig=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(8*1024*1024),b""):
            dig.update(chunk)
    return dig.hexdigest()

def parse(path):
    h=read_prefix(path)
    if len(h)<3*SECTOR: raise ValueError('image prefix truncated')
    hdr=bytearray(h[SECTOR:2*SECTOR]);
    if hdr[:8]!=b'EFI PART': raise ValueError('no GPT header')
    sz=struct.unpack_from('<I',hdr,12)[0]
    if sz<92 or sz>SECTOR: raise ValueError('invalid header length')
    saved=struct.unpack_from('<I',hdr,16)[0]; struct.pack_into('<I',hdr,16,0)
    if zlib.crc32(hdr[:sz])&0xffffffff!=saved: raise ValueError('primary GPT header CRC mismatch')
    current,backup,first,last=struct.unpack_from('<QQQQ',hdr,24)
    part_lba=struct.unpack_from('<Q',hdr,72)[0]
    count,entry_size,entry_crc=struct.unpack_from('<III',hdr,80)
    if (current,part_lba,entry_size,count)!=(1,2,128,128):raise ValueError('unsupported GPT layout')
    entries=h[2*SECTOR:2*SECTOR+count*entry_size]
    if zlib.crc32(entries)&0xffffffff!=entry_crc:raise ValueError('GPT entry array CRC mismatch')
    if (backup+1)*SECTOR!=IMAGE:raise ValueError('unexpected source disk size')
    if (backup+1)*SECTOR>TARGET:raise ValueError('source larger than target')
    max_end=0; parts=[]
    for i in range(count):
        e=entries[i*entry_size:(i+1)*entry_size]
        if e[:16]==bytes(16):continue
        start,end=struct.unpack_from('<QQ',e,32)
        if not first<=start<=end<=last:raise ValueError('partition outside source usable LBAs')
        max_end=max(max_end,end)
        parts.append({'index':i+1,'first_lba':start,'last_lba':end})
    if len(parts)!=3 or parts[0]['index']!=1:raise ValueError('expected exactly three partitions')
    target_last=TARGET//SECTOR-1
    backup_entries_sectors=(len(entries)+SECTOR-1)//SECTOR
    target_backup_entries=target_last-backup_entries_sectors
    target_last_usable=target_backup_entries-1
    if max_end>target_last_usable:raise ValueError('partition overlaps target backup GPT')
    return {'source_image':str(path),'source_bytes':IMAGE,'target_bytes':TARGET,'sector_size':SECTOR,
            'source_backup_gpt_lba':backup,'target_backup_gpt_lba':target_last,
            'target_backup_table_lba':target_backup_entries,'new_last_usable_lba':target_last_usable,
            'source_entry_array_crc32':f'{entry_crc:08x}','partitions':parts,
            'compressed_image_sha256':file_sha256(path),
            'plan_only':True,'writes_performed':False}

def main():
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('image',type=pathlib.Path)
    args=a.parse_args(); print(json.dumps(parse(args.image),indent=2))
if __name__=='__main__':
    try:main()
    except (OSError,ValueError,subprocess.SubprocessError) as e:print('FAIL:',e,file=sys.stderr);sys.exit(1)
