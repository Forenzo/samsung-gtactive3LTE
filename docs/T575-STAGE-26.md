# SM-T575 LTE — Stage 26: nested Android DT tables

Stage 25 has now passed after the parser was corrected. The owner verified:

- BOOT Android header v2; DT segment at offset **33,748,992**, length **189,700**.
- The first four bytes at this offset are `d7b7ab1e` — Android DT table magic,
  rather than direct raw-FDT magic. The first valid FDT is at segment offset
  **64**, size **189,636**, version 17.
- DTBO table has six overlays; the historically selected index **5** is a
  valid version-17 FDT of **119,332** bytes.

Stage 26 adds `scripts/t575-stage26-dt-tables.py` to explicitly parse the
BOOT embedded Android DT table and all six DTBO table entries. It checks
container geometry, FDT boundaries and non-overlap, without extracting or
displaying proprietary device-tree properties.

From the Mac, with existing private backups:

```sh
cd ~/samsung-gtactive3LTE
python3 -m py_compile scripts/t575-stage26-dt-tables.py
python3 scripts/t575-stage26-dt-tables.py
```

The selected overlay index defaults to 5 based on an **earlier** stock
Android boot argument. Stage 26 does not newly establish the selection
or apply overlays to the embedded base tree. It does not contact the
tablet, modify backup images, generate Linux boot files, or flash.

**Next meaningful engineering question:** Compare a safely constructed,
offline representation of the base DT plus overlay #5 against the
already captured live Android DT, taking care not to put vendor blobs
or device-unique identifiers into public GitHub. A static comparison
does not verify S-Boot display scanout or a tested non-wiping restore.

**The BOOT / FLASH gate remains BLOCKED.**
