#!/usr/bin/env python3
"""Read-only checks for essential Linux DTB device descriptions on SM-T575.

These checks compare known stock SM-T575 hardware addresses to the compiled
*Linux* DTB. They do not test device drivers or authorize boot/flashing.
The private Samsung FDT is never uploaded to CI.
"""
import runpy
import struct
import sys
from pathlib import Path

def val32(b):
    return struct.unpack(">I", b)[0]

def audit(path):
    parse = runpy.run_path(str(Path(__file__).with_name("audit-t575-memory.py")))["parse"]
    nodes = parse(path)
    issues = []
    def named_chip(suffix, kind):
        results = [(n,p) for n,p in nodes.items() if n.lower().endswith(suffix.lower())]
        if not results:
            issues.append(f"{kind}: expected node ending {suffix} missing")
            return None
        if len(results) > 1:
            issues.append(f"{kind}: multiple ambiguous {suffix} nodes")
            return None
        n,p = results[0]
        print(f"{kind}: {n} compatible={p.get('compatible',b'').split(bytes([0]))[0].decode(errors='replace')} status={p.get('status',b'okay').decode(errors='replace').strip(chr(0))}")
        if p.get("status", b"okay").rstrip(bytes([0])) == b"disabled":
            issues.append(f"{kind}: disabled")
        return p

    # These SoC controller register bases were confirmed in the stock FDT.
    usb = named_chip("@10c00000", "USB DWC3 parent")
    ufs = named_chip("@11120000", "UFS host")
    # The downstream USB DWC3 node is nested, and mainline's node is also
    # nested. Verify a DWC3 compatible exists anywhere in the resulting DTB.
    if not any(b"dwc3" in p.get("compatible",b"").lower() for p in nodes.values()):
        issues.append("USB: no DWC3 compatible found")
    # Vendor panel is 1200x1920. Mainline bring-up relies on S-Boot's
    # preinitialized simple framebuffer rather than a native display driver.
    displays=[(n,p) for n,p in nodes.items() if b"simple-framebuffer" in p.get("compatible",b"")]
    if len(displays)!=1:
        issues.append(f"Display: expected one simple-framebuffer, found {len(displays)}")
    else:
        name,p=displays[0]
        width=val32(p["width"]) if len(p.get("width",b""))==4 else None
        height=val32(p["height"]) if len(p.get("height",b""))==4 else None
        print(f"Boot framebuffer: {name} {width}x{height}")
        if (width,height)!=(1200,1920):
            issues.append("Display: boot framebuffer dimensions differ from Samsung stock")
        if "memory-region" not in p:
            issues.append("Display: framebuffer has no memory-region reservation link")
    # The Linux board DTB must carry board identification.
    root=nodes.get("/",{})
    if b"samsung,gtactive3lte" not in root.get("compatible",b""):
        issues.append("Board: SM-T575 compatible missing")
    for issue in issues:
        print("ERROR:",issue,file=sys.stderr)
    if issues:
        return 1
    print("PASS: DTB describes essential USB, UFS and boot framebuffer basics.")
    print("NOTE: no runtime driver tests, panel power check or USB enumeration performed.")
    return 0

if __name__=="__main__":
    if len(sys.argv)!=2:
        print("Usage: audit-t575-boot-basics.py compiled.dtb",file=sys.stderr)
        sys.exit(2)
    try:
        sys.exit(audit(sys.argv[1]))
    except (ValueError, KeyError, OSError, struct.error) as error:
        print(f"Audit error: {error}",file=sys.stderr)
        sys.exit(1)
