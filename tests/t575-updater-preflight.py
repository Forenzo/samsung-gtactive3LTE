#!/usr/bin/env python3

import os
import pathlib
import struct
import subprocess
import tempfile

repo = pathlib.Path(__file__).resolve().parents[1]

with tempfile.TemporaryDirectory() as tmp:
    root = pathlib.Path(tmp)
    out = root / "images"
    out.mkdir()

    name = "samsung-gtactive3-lte_phosh_edge_26112501"
    h = "3" * 32 + "4" * 32

    (out / f"{name}.efi").write_bytes(
        b"usrhash=" + h.encode() + b"\n"
    )

    (out / f"{name}.usr-arm64.{h[:32]}.raw").write_bytes(
        bytes(4096)
    )

    verity = bytearray(4096)
    verity[:8] = b"verity\0\0"
    struct.pack_into("<IIQ", verity, 64, 4096, 4096, 1)

    (out / f"{name}.usr-arm64-verity.{h[32:]}.raw").write_bytes(
        verity
    )

    mock = root / "ssh"

    mock.write_text("""#!/bin/bash
case "${!#}" in
    "cat /usr/lib/os-release")
        if [ "$TEST_CASE" = wrong_model ]; then
            echo IMAGE_ID=samsung-gtactive3-wifi
        else
            echo IMAGE_ID=samsung-gtactive3-lte
        fi
        ;;
    "cat /proc/version")
        echo "Linux 7.3.0 postmarketOS"
        ;;
    "cat /proc/cmdline")
        echo "usrhash=1111111111111111111111111111111122222222222222222222222222222222"
        ;;
    /usr/bin/lsblk*)
        U=duranium_26111790_usr
        V=duranium_26111790_vty
        SIZE=1048576

        case "$TEST_CASE" in
            foreign) U=cairn-root ;;
            mismatched) V=duranium_26111791_vty ;;
            too_small) SIZE=1024 ;;
            empty) U=_empty; V=_empty ;;
            wrong_role) U=duranium_26111790_vty ;;
        esac

        cat <<EOF
NAME="loop0p1" PARTLABEL="duranium_26111789_usr" PARTTYPE="b0e01050-ee5f-4390-949a-9101b17104e9" PARTUUID="11111111-1111-1111-1111-111111111111" SIZE="1048576"
NAME="loop0p2" PARTLABEL="duranium_26111789_vty" PARTTYPE="6e11a4e7-fbca-4ded-b9e9-e1a512bb664e" PARTUUID="22222222-2222-2222-2222-222222222222" SIZE="1048576"
NAME="loop0p3" PARTLABEL="$U" PARTTYPE="b0e01050-ee5f-4390-949a-9101b17104e9" PARTUUID="55555555-5555-5555-5555-555555555555" SIZE="$SIZE"
NAME="loop0p4" PARTLABEL="$V" PARTTYPE="6e11a4e7-fbca-4ded-b9e9-e1a512bb664e" PARTUUID="66666666-6666-6666-6666-666666666666" SIZE="$SIZE"
EOF
        ;;
    *)
        echo "BLOCKED unexpected remote operation" >&2
        exit 99
        ;;
esac
""")

    mock.chmod(0o755)

    tests = {
        "valid": (True, "PASS: update preflight"),
        "empty": (True, "PASS: update preflight"),
        "wrong_model": (False, "Image identity mismatch"),
        "foreign": (False, "Refusing foreign"),
        "mismatched": (False, "versions do not match"),
        "too_small": (False, "images larger"),
        "wrong_role": (False, "do not form a valid pair"),
    }

    for case, (success, expected) in tests.items():
        env = dict(os.environ)

        env.update(
            PATH=f"{root}:{env['PATH']}",
            GTA3_SSH="offline-test",
            IMAGE="samsung-gtactive3-lte",
            UI="phosh",
            OUT=str(out),
            EXTENSIONS="",
            APPLY="0",
            TEST_CASE=case
        )

        r = subprocess.run(
            ["bash", "scripts/duranium-update", "26112501"],
            cwd=repo,
            env=env,
            capture_output=True,
            text=True,
            timeout=30
        )

        output = r.stdout + r.stderr

        assert (r.returncode == 0) == success, output
        assert expected in output, output
        assert "BLOCKED" not in output, output

        print("PASS:", case)

print("PASS: all seven simulated updater tests")
