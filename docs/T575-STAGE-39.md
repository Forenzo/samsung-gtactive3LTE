# Stage 39 — verify the TAS2562 sound-DAI reference from UAIF1

## Stage 38 result (owner-run)

The owner confirmed exactly one phandle-reference candidate in the
reconstructed Android BOOT + DTBO #5 sound tree:

`/sound/uaif@1/codec :: sound-dai`

The TAS2562 codec node had a valid phandle, and the scan found one
matching 32-bit cell. This provides strong evidence for UAIF1 linkage,
but a matching cell alone is insufficient to establish DAI tuple
semantics or working Linux audio.

## Stage 39 offline validation

The new `scripts/t575-stage39-uaif1-tuple.py` uses the existing
bounded Stage 38 FDT parser to inspect just the private merged FDT.
It checks the `sound-dai` property on `/sound/uaif@1/codec` is
exactly two 32-bit cells, the first references TAS2562, and the
remaining cell is a DAI index. The result is printed without exposing
raw proprietary DTS data or unrelated property values.

```sh
cd ~/samsung-gtactive3LTE
git pull origin port/sm-t575-bringup
python3 -m py_compile scripts/t575-stage39-uaif1-tuple.py
python3 scripts/t575-stage39-uaif1-tuple.py
```

The script makes only private temporary files for offline `fdtoverlay`
and deletes them before exit. The Android tablet need not be connected.

An exact tuple match does not establish clock configuration, routing,
power, ABOX compatibility, or driver operation. Continue keeping
the inherited T570 sound configuration and DECON takeover disabled.
Verified non-wiping T575 Download-mode recovery remains a required
prerequisite for experimental Linux boot.

**RESTORE / BOOT / FLASH GATE: BLOCKED.**
