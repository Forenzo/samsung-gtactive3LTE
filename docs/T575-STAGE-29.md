# SM-T575 LTE Stage 29 — offline selected-overlay merge

## Evidence from Stage 28

Owner-run offline inspection of the verified BOOT and DTBO backup images
found an 854-node base FDT and an 813-node DTBO #5 with 146 overlay
fragments. Base DSIM1 (0x16090000) is explicitly disabled and DECON-F,
DECON-T, DSIM0, ABOX and reserved modem memory nodes exist. DTBO #5
contains an HX83102E panel node and audio definitions, including
TAS2562 and RT5510, plus explicitly okay sound/dummy audio nodes.

**Important:** per-source-tree status is not merged runtime status.
An overlay can change base properties and phandle targets; presence
alone does not prove hardware enabled or a working Linux driver.

## Stage 29

The offline script `scripts/t575-stage29-offline-overlay-merge.py`
extracts the base FDT and historically selected DTBO #5 into a
mode-0700 private temporary directory and calls `fdtoverlay` from the
device-tree compiler (dtc) package. It scans only selected merged node
names and their `status` properties, then automatically deletes the
temporary directory. It never contacts the tablet, modifies original
backups, writes to the repository, or publishes vendor DT contents.

Run on macOS:

```sh
cd ~/samsung-gtactive3LTE
python3 -m py_compile scripts/t575-stage29-offline-overlay-merge.py
python3 scripts/t575-stage29-offline-overlay-merge.py
```

If the tool reports missing `fdtoverlay`, install `dtc` via
Homebrew (e.g. `brew install dtc`) and rerun. A merge error is
diagnostic, not evidence that Android is broken: Samsung's bootloader
may perform transformations or apply overlays differently. Also,
historical `androidboot.dtbo_idx=5` has not been rechecked.

**Even a successful merged FDT is not a boot candidate.**
Recovery via non-wiping Download-mode restore, stock firmware,
bootloader state, and Samsung display handover remain unverified.
**FLASH/BOOT GATE: BLOCKED.**
