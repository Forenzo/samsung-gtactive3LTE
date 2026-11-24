#!/usr/bin/env python3
"""Read-only audit of tracked text files for literal network IP addresses.

Searches all Git-tracked files, including vendored bootchain and patch trees.
Reports filenames and address classification ONLY; never prints IP values.
Does not inspect Git history, remote branches, GitHub Actions logs or Git LFS objects.
"""
from __future__ import annotations
import collections
import ipaddress
import pathlib
import re
import subprocess

ipv4 = re.compile(rb"(?<![0-9.])(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?![0-9.])")
ipv6 = re.compile(rb"(?<![0-9A-Fa-f:])(?:[0-9A-Fa-f]{0,4}:){2,}[0-9A-Fa-f:]{0,39}(?![0-9A-Fa-f:])")
paths = subprocess.check_output(["git", "ls-files", "-z"]).split(b"\0")
counts: dict[str, collections.Counter[str]] = {}
scanned = 0
for item in paths:
    if not item:
        continue
    path = pathlib.Path(item.decode("utf-8", errors="surrogateescape"))
    try:
        data = path.read_bytes()
    except (OSError, IsADirectoryError):
        continue
    scanned += 1
    if b"\0" in data[:8192]:
        continue
    found = collections.Counter()
    for regex in (ipv4, ipv6):
        for m in regex.finditer(data):
            try:
                addr = ipaddress.ip_address(m.group().decode("ascii"))
            except ValueError:
                continue
            category = (
                "loopback" if addr.is_loopback else
                "link-local" if addr.is_link_local else
                "private" if addr.is_private else
                "multicast" if addr.is_multicast else
                "public"
            )
            found[f"IPv{addr.version} {category}"] += 1
    if found:
        counts[path.as_posix()] = found

print(f"Scanned {scanned} tracked paths; {len(counts)} contain network address literals")
summary = collections.Counter()
for path, categories in sorted(counts.items()):
    section = (
        "vendored bootchain" if path.startswith("bootchain/") else
        "kernel/patches" if path.startswith("patches/") else
        "system packaging" if path.startswith("pmos/") else
        "first-party other"
    )
    summary[section] += 1
    details = ", ".join(f"{name}={count}" for name, count in sorted(categories.items()))
    print(f"{section}: {path}: {details}")
print("Summary (files with hits):", dict(summary))
print("No address strings were printed by this audit.")
