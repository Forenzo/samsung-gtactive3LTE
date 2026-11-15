#!/usr/bin/env python3
"""Read-only SHA256 and embedded .modinfo audit of the NFS modules artifact.

No network actions, no device access, no extraction, no insmod/flash.
Usage: python3 first-gui/audit-nfs-modules.py ~/Downloads/ARTIFACT.zip
"""
import argparse
import hashlib
import pathlib
import re
import sys
import zipfile

START = ("nfs", "nfsv3")
EXPECTED_VERMAGIC = "7.3.0 SMP preempt mod_unload aarch64"


def read_modinfo(data):
    # The uncompressed ELF module has a NUL-delimited .modinfo section.
    # Extract only key-value substrings bounded by NUL. Values are untrusted.
    out = {}
    for value in data.split(b"\0"):
        for key in (b"vermagic=", b"depends=", b"name=", b"intree="):
            if value.startswith(key):
                try:
                    out[key[:-1].decode()] = value[len(key):].decode("ascii")
                except UnicodeDecodeError:
                    raise ValueError("Non-ASCII module metadata")
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("zip", type=pathlib.Path)
    args = p.parse_args()
    zpath = args.zip.expanduser()
    if not zpath.is_file():
        raise ValueError(f"ZIP not found: {zpath}")
    with zipfile.ZipFile(zpath) as z:
        names = z.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Duplicate ZIP member names")
        modules = {}
        for name in names:
            if name.startswith("modules/") and name.endswith(".ko"):
                modname = pathlib.PurePosixPath(name).stem
                if modname in modules:
                    raise ValueError(f"Duplicate module name: {modname}")
                modules[modname] = (name, z.read(name))
        if not modules:
            raise ValueError("No modules found")
        manifest = z.read("SHA256SUMS").decode("ascii")
        checksums = {}
        for line in manifest.splitlines():
            pieces = line.split()
            if len(pieces) != 2 or not re.fullmatch("[0-9a-fA-F]{64}", pieces[0]):
                raise ValueError("Malformed SHA256SUMS line")
            pathname = pieces[1].lstrip("*")
            if pathname in checksums:
                raise ValueError("Repeated path in SHA256SUMS")
            checksums[pathname] = pieces[0].lower()
        if set(checksums) != {name for name, _ in modules.values()}:
            raise ValueError("Manifest names differ from module members")
        for name, data in modules.values():
            if hashlib.sha256(data).hexdigest() != checksums[name]:
                raise ValueError(f"SHA256 mismatch: {name}")
        print(f"PASS: SHA256 checksums verified for {len(modules)} ELF module files.")
        report = z.read("ABI-REVIEW-REQUIRED.txt").decode("utf-8")
        print("\nBUILD ABI REPORT (claimed by build, not physical compatibility proof)")
        for line in report.splitlines():
            if line == "Experimental build kernel release:" or line.startswith("CONFIG_NFS") or line.startswith("CONFIG_SUNRPC") or line.startswith("CONFIG_LOCKD"):
                print(line)
        for name in START:
            if name not in modules:
                raise ValueError(f"Missing required module {name}.ko")
        details = {}
        for name, (_, data) in modules.items():
            if not data.startswith(b"\x7fELF") or len(data) < 20 or data[4:6] != b"\x02\x01" or int.from_bytes(data[18:20], "little") != 183:
                raise ValueError(f"{name}.ko is not little-endian AArch64 ELF")
            info = read_modinfo(data)
            if info.get("vermagic") != EXPECTED_VERMAGIC:
                raise ValueError(f"{name}: unexpected vermagic {info.get('vermagic')!r}")
            details[name] = info
        print(f"PASS: all module vermagic strings match expected build: {EXPECTED_VERMAGIC}")
        needed = set()
        visiting = set()
        ordered = []
        def visit(name):
            if name in needed:
                return
            if name in visiting:
                raise ValueError(f"Cyclic module dependency at {name}")
            if name not in modules:
                raise ValueError(f"Missing dependency module: {name}")
            visiting.add(name)
            deps = [x for x in details[name].get("depends", "").split(",") if x]
            for dep in deps:
                if dep in modules:
                    visit(dep)
                else:
                    print(f"  EXTERNAL OR BUILT-IN DEPENDENCY: {name} -> {dep}")
            visiting.remove(name)
            needed.add(name)
            ordered.append(name)
        for name in START:
            visit(name)
        print("\nBUILD-DECLARED NFS MODULE DEPENDENCY ORDER:")
        for name in ordered:
            print(f"  {name}.ko  depends={details[name].get('depends', '') or '(none)'}")
        print("\nAUDIT ONLY: matching vermagic is insufficient to establish runtime ABI compatibility.")
        print("DO NOT LOAD on the physical SM-T575 until baseline symbols/config and recovery are reviewed.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, zipfile.BadZipFile, KeyError) as exc:
        sys.exit(f"ERROR: {exc}")
