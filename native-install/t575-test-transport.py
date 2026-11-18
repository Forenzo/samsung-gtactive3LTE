#!/usr/bin/env python3
"""SM-T575 RAM-only USB IPv6 transport test. Absolutely no block-device writes."""
import argparse
import socket
import struct
import zlib

p = argparse.ArgumentParser()
p.add_argument('--host', default='fe80::57:aff:fe00:1')
p.add_argument('--interface', default='en7')
p.add_argument('--port', type=int, default=23456)
a = p.parse_args()
# Reproducible 1 MiB payload; receiver discards the data and replies with CRC32.
block = bytes(range(256)) * 4096
expected = zlib.crc32(block) & 0xffffffff
scope = socket.if_nametoindex(a.interface)
with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as s:
    s.settimeout(45)
    s.connect((a.host, a.port, 0, scope))
    s.sendall(b'T575RAM1' + struct.pack('!I', len(block)))
    s.sendall(block)
    answer = bytearray()
    while len(answer) < 4:
        part=s.recv(4-len(answer))
        if not part: raise RuntimeError('Receiver closed without a checksum')
        answer += part
actual = struct.unpack('!I', answer)[0]
print('SM-T575 RAM-ONLY USB TRANSPORT:','PASS' if actual == expected else 'FAIL')
print(f'Payload bytes: {len(block)}; local CRC32: {expected:08x}; tablet CRC32: {actual:08x}')
if actual != expected: raise SystemExit(1)
