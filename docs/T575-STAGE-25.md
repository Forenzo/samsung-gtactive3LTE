# SM-T575 LTE Stage 25 — offline BOOT and selected DTBO FDT validation

## Stage 24 evidence

The owner ran the offline Android BOOT/DTBO structure audit successfully:
- BOOT partition backup: 61,865,984 bytes, Android header v2, page 2048.
- kernel 32,194,592 bytes; ramdisk 1,549,209 bytes.
- embedded DTB segment: 189,700 bytes.
- DTBO backup: 8,388,608 bytes; table header 32 bytes, six 32-byte entries,
  total payload/table length 709,380 bytes.
- all six overlays passed the structural bounds/magic checks.

## Stage 25

`scripts/t575-stage25-dt-structure.py` independently checks the BOOT
embedded flattened-device-tree header and the selected DTBO payload FDT
header, including their structure/string/reservation offsets and bounds.
The default selected overlay is index **5**, from the owner's earlier
Android `androidboot.dtbo_idx=5` evidence. The current runtime selection
has not been re-read by this offline test.

On the Mac:

```bash
cd ~/samsung-gtactive3LTE
python3 scripts/t575-stage25-dt-structure.py
```

The tool reads only the two existing private backup files in
`~/Downloads/SM-T575-Recovery`. It does not decode or print unique
identifiers, extract DTS/DTBO contents, create any files, use ADB, or
alter the tablet. A structural PASS does not establish that the selected
overlay is the right revision or has compatible mainline Linux bindings.

## Remaining boot blockers

Verified copies of the installed Android BOOT and DTBO exist, but their
restoration via Download mode without wiping has **not** been tested.
Actual S-Boot scanout and DECON/DSI handover state remain unverified;
the T570 installer is not suitable for the T575. **Do not flash.**
