#!/usr/bin/env python3
"""Inspect a complete generated Linux .config; do not make device changes."""
from pathlib import Path
import sys

KEYS = (
    "CONFIG_INET",
    "CONFIG_IPV6",
    "CONFIG_USB_CONFIGFS",
    "CONFIG_USB_CONFIGFS_NCM",
    "CONFIG_NFS_FS",
    "CONFIG_NFS_V3",
    "CONFIG_SUNRPC",
    "CONFIG_LOCKD",
    "CONFIG_TMPFS",
    "CONFIG_DEVTMPFS",
    "CONFIG_DRM",
    "CONFIG_DRM_EXYNOS9810_DPU",
    "CONFIG_DRM_PANFROST",
)

def parse(path):
    result = {}
    for line in Path(path).read_text().splitlines():
        if "=" in line and line.startswith("CONFIG_"):
            k, val = line.split("=", 1)
            result[k] = val
        elif line.startswith("# CONFIG_") and line.endswith(" is not set"):
            result[line[2:].split(" ", 1)[0]] = "n"
    return result

if len(sys.argv) != 2:
    sys.exit("usage: audit-netroot-config.py PATH_TO_GENERATED_DOT_CONFIG")
cfg = parse(sys.argv[1])
for k in KEYS:
    print(f"{k}={cfg.get(k, 'MISSING')}")
base = (
    "CONFIG_USB_CONFIGFS_NCM",
    "CONFIG_TMPFS",
    "CONFIG_DEVTMPFS",
    "CONFIG_DRM_EXYNOS9810_DPU",
)
if any(cfg.get(k) != "y" for k in base):
    sys.exit("FAIL: existing diagnostic boot prerequisites missing")
nfs = ("CONFIG_NFS_FS", "CONFIG_NFS_V3", "CONFIG_SUNRPC", "CONFIG_LOCKD")
if all(cfg.get(k) == "y" for k in nfs):
    print("NETROOT NFSv3 CLIENT: AVAILABLE (not tested on device)")
else:
    print("NETROOT NFSv3 CLIENT: NOT READY; use experimental config and rebuild")
print("BOOT/FLASH: NOT PERFORMED")
