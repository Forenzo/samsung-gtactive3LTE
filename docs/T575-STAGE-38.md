# Stage 38 — trace TAS2562 reference candidates in the merged ABOX/sound tree

## Confirmed Stage 37 results

On the owner's rooted SM-T575 stock Android BOOT+DTBO #5, offline
reconstruction showed `/hsi2c@108C0000/tas2562@4c` with:
- `compatible` containing `ti,tas2562`;
- first `reg` cell 0x4c;
- `#sound-dai-cells = <1>`;
- explicit `status=ok` and parent I2C controller `status=okay`;
- no explicit interrupt, reset, or shutdown GPIO properties.

These are strong **vendor DT compatibility clues** but not verification
of the Linux ASoC sound-card path, power sequencing or the mainline
machine driver's compatibility.

## Stage 38

This offline script checks whether the merged codec node has a
`phandle` (or `linux,phandle`) and scans FDT properties under
`/sound`, `/abox` and related audio node names for 32-bit cells
equal to that value.

```sh
cd ~/samsung-gtactive3LTE
git pull origin port/sm-t575-bringup
python3 -m py_compile scripts/t575-stage38-audio-phandle-references.py
python3 scripts/t575-stage38-audio-phandle-references.py
```

Only sanitized node paths, property names and match counts are printed;
the phandle value, proprietary device-tree data, identifiers, and other
property values are withheld. It uses owner-private backup images,
`fdtoverlay` and a private automatically deleted temporary directory.
No device connected, no source DTS changed.

**Important interpretation:** matching a 32-bit cell is a candidate
reference, not by itself proof of a valid sound DAI phandle or playable
audio. A zero-result does not prove the codec isn't connected: vendor
Samsung ASoC descriptors may use indirect or nonstandard linkage.

Next only after observing output: inspect relevant whitelisted
sound-DAI property formats and upstream Exynos ABOX machine support,
while keeping inherited T570 sound disabled. No first Linux boot
until a proven non-wiping recovery path and safe display handover.

**RESTORE/BOOT/FLASH GATE: BLOCKED.**
