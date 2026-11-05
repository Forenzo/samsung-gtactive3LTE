# Stage 30 — focused merged FDT and Android overlay selection

## Stage 29 evidence (owner-run PASS)

The offline overlay #5 merge succeeded and produced 1,284 FDT nodes.
Compared with the BOOT base FDT, `dsim@0x16090000` changed from
`status=disabled` to `status=okay`. The merged tree includes an
HX83102E panel, `sound` status `okay`, a TAS2562 amplifier
`status=ok`, `etspi-spi@0`, and reserved-memory modem nodes.
These are useful vendor configuration clues, **not** proof of a
functional mainline driver or the tablet's display handover state.

## Stage 30

`scripts/t575-stage30-merged-hardware-and-runtime-index.py`
reconstructs the merge privately, reports specifically named display,
audio and modem nodes and their merged `status` values, and optionally
queries the *running* SM-T575 Android for its selected DTBO index.

The read-only runtime query requires exactly one authorized ADB device
with model `SM-T575`. It checks `ro.boot.dtbo_idx` then, if needed,
reads `/proc/cmdline` in memory to extract **only** the numeric
`androidboot.dtbo_idx` (does not print the complete boot arguments,
serial numbers or other identifiers). If absent or no device, index
is UNKNOWN; do not treat older index 5 as confirmed.

```sh
cd ~/samsung-gtactive3LTE
python3 -m py_compile scripts/t575-stage30-merged-hardware-and-runtime-index.py
python3 scripts/t575-stage30-merged-hardware-and-runtime-index.py
```

Use `--offline` to skip ADB. Private temporary FDTs are deleted when
the process exits; the two validated backups are never modified.
No partition writes, modem access, MMIO probing, or flashing.

Even if the runtime index matches 5, an offline merged FDT is **not**
a tested boot image and does not replace the need for proven non-wiping
recovery, proper bootloader state, and display takeover research.

**RESTORE/BOOT/FLASH GATE: BLOCKED.**
