#!/usr/bin/env python3
"""Stage 14: source-level audit for pinned Linux simpledrm DT handover.

Run against the same *patched* kernel tree used to compile the LTE DTB.
Checks the known code path; this cannot verify S-Boot scanout at runtime.
"""
import sys
from pathlib import Path

def main(kernel_root):
    root = Path(kernel_root)
    driver = root / "drivers/gpu/drm/sysfb/simpledrm.c"
    binding = root / "Documentation/devicetree/bindings/display/simple-framebuffer.yaml"
    errors = []
    for path in (driver, binding):
        if not path.is_file():
            errors.append(f"missing source: {path}")
    if errors:
        for e in errors:
            print("ERROR:", e, file=sys.stderr)
        return 1

    code = driver.read_text(encoding="utf-8")
    schema = binding.read_text(encoding="utf-8")
    expected_driver = {
        "Device Tree compatible": '.compatible = "simple-framebuffer"',
        "reserved-memory resource conversion": "of_reserved_mem_region_to_resource(",
        "fallback framebuffer resource": "platform_get_resource(pdev, IORESOURCE_MEM, 0)",
        "mapped framebuffer": "devm_ioremap_wc(",
    }
    expected_binding = {
        "memory-region binding": "  memory-region:",
        "reserved-memory override": 'overrides the "reg" property',
    }
    print("Stage 14 — pinned kernel simpledrm source audit")
    for name, needle in expected_driver.items():
        ok = needle in code
        print(f"  {name}: {'present' if ok else 'MISSING'}")
        if not ok:
            errors.append(f"driver code path changed: {name}")
    for name, needle in expected_binding.items():
        ok = needle in schema
        print(f"  {name}: {'present' if ok else 'MISSING'}")
        if not ok:
            errors.append(f"DT binding changed: {name}")
    # Source audit is conservative: it is intentionally not a proof that
    # a successful DRM probe or live scanout will occur on LTE hardware.
    if errors:
        for e in errors:
            print("ERROR:", e, file=sys.stderr)
        return 1
    print("PASS: the pinned kernel includes the expected simpledrm DT code paths.")
    print("UNVERIFIED: firmware scanout, panel clocks, register ownership, Linux boot.")
    print("NO flash approval.")
    return 0

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: audit-t575-simpledrm-source.py /path/to/patched/kernel", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
