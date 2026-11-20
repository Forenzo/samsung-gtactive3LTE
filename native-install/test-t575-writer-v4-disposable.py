#!/usr/bin/env python3
"""Linux-only disposable-file integration test for the existing v4 C writer.

This creates a TEST-ONLY transformed copy of the source in a TemporaryDirectory:
all /dev and sysfs paths point into that directory; every disk size is small;
IPv6 localhost is allowed for tests. NEVER deploy this transformed binary.
Requires gcc and Linux headers, runs offline and without root.
"""
import argparse
import hashlib
import os
from pathlib import Path
import socket
import struct
import subprocess
import tempfile
import time
import zlib

SMALL_TARGET = 8 * 1024 * 1024
SMALL_IMAGE = 3 * 1024 * 1024
TOKEN = 'abcdef0123456789abcdef0123456789'
MAGIC = b'T575WR4!'

def replace_once(source, before, after):
    count = source.count(before)
    if count != 1:
        raise AssertionError(f'Unexpected original source: {before!r} (count={count})')
    return source.replace(before, after, 1)

def recv_exact(sock, n):
    chunks = bytearray()
    while len(chunks) < n:
        block = sock.recv(n - len(chunks))
        if not block: raise AssertionError('Receiver disconnected')
        chunks += block
    return bytes(chunks)

def start(binary):
    proc = subprocess.Popen([str(binary), '--arm', TOKEN], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = proc.communicate(timeout=5)
    assert proc.returncode == 0, (out, err)
    assert b'ARMED' in out, out
    # Double-forked child starts listening; retry connections until available.
    for _ in range(50):
        try:
            sock = socket.create_connection(('::1', 23457), timeout=.25)
            sock.settimeout(5)
            return sock
        except (OSError, TimeoutError):
            time.sleep(.05)
    raise AssertionError('Disposable receiver did not open a loopback socket')

def packet(sock, kind, offset, blob):
    sock.sendall(kind + struct.pack('!QI', offset, len(blob)) + blob)
    expected = b'K' + struct.pack('!I', zlib.crc32(blob) & 0xffffffff)
    actual = recv_exact(sock, 5)
    assert actual == expected, (kind, offset, actual.hex(), expected.hex())

def run(source_file):
    with tempfile.TemporaryDirectory(prefix='t575-writer-DISPOSABLE-') as d:
        temp = Path(d)
        source = source_file.read_text()
        source = replace_once(source, '#define TARGET 55461281792ULL', f'#define TARGET {SMALL_TARGET}ULL')
        # Normalize the old v4 size-unit bug if testing an older source.
        source = source.replace('strtoull(b,NULL,10)!=TARGET', 'strtoull(b,NULL,10)!=(TARGET/512ULL)')
        source = replace_once(source, '#define IMAGE 6862950400ULL', f'#define IMAGE {SMALL_IMAGE}ULL')
        source = replace_once(source, '55461261312ULL,55461277696ULL', f'{SMALL_TARGET-20480}ULL,{SMALL_TARGET-4096}ULL')
        source = replace_once(source, 'if(IN6_IS_ADDR_LINKLOCAL(&peer.sin6_addr))', 'if(IN6_IS_ADDR_LOOPBACK(&peer.sin6_addr))')
        source = replace_once(source, 'bindaddr.sin6_addr=in6addr_any;', 'bindaddr.sin6_addr=in6addr_loopback;')
        source = replace_once(source,
            'if(ioctl(fd,BLKGETSIZE64,&bytes)||ioctl(fd,BLKSSZGET,&sec)||bytes!=TARGET||sec!=(int)SECTOR)goto done;',
            'bytes=TARGET;sec=SECTOR; if(bytes!=TARGET||sec!=(int)SECTOR)goto done;')
        # Read-only mock sysfs; pathname rewritten only in disposable test executable.
        mappings = {
            '/proc/device-tree/model': 'sys/model',
            '/sys/class/block/sda31/uevent': 'sys/uevent',
            '/sys/class/block/sda31/size': 'sys/size',
            '/sys/block/sda/queue/logical_block_size': 'sys/logical_block_size',
            '/proc/mounts': 'sys/mounts',
            '/dev/sda31': 'disposable.img',
        }
        for old, new in mappings.items():
            source = source.replace('"'+old+'"', '"'+str(temp/new)+'"')
        fixture = temp/'sys'; fixture.mkdir()
        (fixture/'model').write_text('Samsung Galaxy Tab Active3 LTE (SM-T575)')
        (fixture/'uevent').write_text('PARTNAME=userdata\n')
        (fixture/'size').write_text(str(SMALL_TARGET//512)+'\n')
        (fixture/'logical_block_size').write_text('4096\n')
        (fixture/'mounts').write_text('')
        img = temp/'disposable.img'
        with img.open('wb') as f: f.truncate(SMALL_TARGET)
        c_file=temp/'TEST-ONLY-writer.c'; c_file.write_text(source)
        exe=temp/'TEST-ONLY-writer'
        subprocess.run(['gcc','-O2','-Wall','-Wextra','-Werror','-o',str(exe),str(c_file)],check=True)
        data = bytes(range(256)) * (SMALL_IMAGE//256)
        patches = [
            (0, b'M'*4096), (4096,b'G'*4096),
            (SMALL_TARGET-20480,b'T'*16384), (SMALL_TARGET-4096,b'B'*4096),
        ]
        with start(exe) as sock:
            sock.sendall(MAGIC + TOKEN.encode() + struct.pack('!Q',SMALL_IMAGE))
            assert recv_exact(sock, 2) == b'GO'
            for i in range(0,len(data),1024*1024):
                packet(sock,b'D',i,data[i:i+1024*1024])
            for offset, contents in patches:
                packet(sock,b'P',offset,contents)
            sock.sendall(b'F'+struct.pack('!QI',0,0))
            assert recv_exact(sock, 4) == b'DONE'
        expected=bytearray(SMALL_TARGET)
        expected[:SMALL_IMAGE]=data
        for offset, contents in patches:expected[offset:offset+len(contents)]=contents
        actual=img.read_bytes()
        assert actual==expected, 'DISPOSABLE target bytes differed from expected image+patches'
        print('PASS: v4 protocol streamed 3 MiB through real compiled C receiver')
        print('PASS: four GPT patch extents checked and written in required order')
        print('PASS: each chunk acknowledged with read-back CRC32')
        print('PASS: final fsync acknowledgment and full disposable-file SHA256')
        print('SHA256:',hashlib.sha256(actual).hexdigest())
        print('NO TABLET CONNECTIONS, NO TABLET WRITES')

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--source',type=Path,default=Path('native-install/t575-writer-v4.c'))
    a=p.parse_args()
    run(a.source)
