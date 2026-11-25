#!/usr/bin/env python3

from pathlib import Path
import hashlib
import subprocess
import re
import sys

root = Path(__file__).resolve().parents[1] / "pmos/aports"

fix_order = "--fix-order" in sys.argv

pending = []
errors = []

for p in sorted(root.rglob("APKBUILD")):

    text = p.read_text()

    if 'sha512sums="' not in text:
        continue

    evaluated = subprocess.check_output(
        [
            "bash", "-c",
            'set -e; . ./APKBUILD >/dev/null; '
            'printf "%s\\0%s" "$source" "$sha512sums"'
        ],
        cwd=p.parent
    ).decode()

    source, checksums = evaluated.split("\0", 1)

    sources = source.split()

    match = re.search(
        r'(?ms)^sha512sums="\n(.*?)^"',
        text
    )

    assert match, p

    raw_lines = [
        line for line in match.group(1).splitlines()
        if line.strip()
    ]

    expanded_lines = [
        line for line in checksums.splitlines()
        if line.strip()
    ]

    assert len(raw_lines) == len(expanded_lines), p

    sums = {}

    for raw, expanded in zip(raw_lines, expanded_lines):

        digest, name = expanded.split()

        assert name not in sums, (p, name)
        assert re.fullmatch(r"[a-f0-9]{128}", digest)

        sums[name] = (digest, raw)

    ordered = []
    names = []

    for src in sources:

        if "::" in src:
            name = src.split("::", 1)[0]
        else:
            name = src.rsplit("/", 1)[-1]

        names.append(name)

        if name not in sums:
            errors.append(f"{p}: missing checksum: {name}")
            continue

        digest, raw = sums[name]

        if "://" not in src:

            local = p.parent / src

            if not local.is_file():
                errors.append(f"{p}: missing source: {src}")

            elif hashlib.sha512(
                local.read_bytes()
            ).hexdigest() != digest:
                errors.append(f"{p}: checksum mismatch: {src}")

        ordered.append(raw)

    if len(sources) != len(sums):
        errors.append(f"{p}: source/checksum count mismatch")

    if set(names) != set(sums):
        errors.append(f"{p}: source/checksum name mismatch")

    block = "".join(line + "\n" for line in ordered)

    if block != match.group(1):

        if fix_order:
            updated = (
                text[:match.start(1)] +
                block +
                text[match.end(1):]
            )

            pending.append((p, updated))

        else:
            errors.append(f"{p}: checksum ordering mismatch")

    print("AUDITED:", p.parent.name)

if errors:

    for error in errors:
        print("FAIL:", error)

    raise SystemExit("STOP: package validation failed")

for p, updated in pending:

    p.write_text(updated)

    print("REORDERED:", p.parent.name)

print("PASS: all local source checksums verified")
print("PASS: source/checksum ordering aligned")
print("PASS: variable-based filenames handled correctly")
print("No existing checksum values replaced by this auditor")
