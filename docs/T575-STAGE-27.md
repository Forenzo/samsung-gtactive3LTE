# Stage 27 — Private FDT hardware-node inventory

## Stage 26 result: PASS

Owner's offline audit confirmed:
- BOOT embedded Android DT table: one FDT, at relative offset 64, length 189,636 bytes.
- DTBO table: six overlays; the historically selected overlay index 5 is
  119,332 bytes, with a valid FDT header.
- Both tables' payload offsets, FDT sizes, and non-overlap checks passed.

## Next step

Stage 27 parses FDT structure *tokens* directly from the existing
private local backup images. It lists matching **node names only**
for display, touchscreen, audio and LTE/modem categories, capped to
35 names per category per tree, without reading or printing any
property values, serials, MAC addresses or firmware contents. It
does not merge the selected overlay into the base tree.

```sh
cd ~/samsung-gtactive3LTE
python3 -m py_compile scripts/t575-stage27-hardware-node-inventory.py
python3 scripts/t575-stage27-hardware-node-inventory.py
```

Defaults to `~/Downloads/SM-T575-Recovery` and historical overlay
index 5. Node presence is **not** proof of working hardware, or even
of an enabled node in the final runtime FDT. The currently selected
overlay is not re-established by the offline inspection.

The first Linux boot remains prohibited until a non-wiping recovery
procedure and Samsung display handover are demonstrably safe.
