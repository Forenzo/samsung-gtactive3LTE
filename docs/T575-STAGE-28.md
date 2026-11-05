# Stage 28 — filtered hardware status and overlay targets

## Stage 27 result (owner-confirmed)

Stage 27 parsed 854 nodes in the private BOOT base tree and 813 nodes
in DTBO overlay #5. Relevant results:

- BOOT base: Samsung DECON-F (`0x16030000`), DECON-T
  (`0x16050000`), DSIM (`0x16080000`, `0x16090000`),
  Samsung ABOX, and modem nodes `modem_if` and `cp_ram_logging`.
- Overlay #5: `decon_board_hx83102e` panel-related node,
  `tas2562@4c` and `rt5510@34` audio-related node names,
  and `etspi-spi@0` nodes.
- The absence of a node-name match for `touch` is **not** proof that
  the touchscreen is absent: it may be named differently.
- The presence of two audio codecs in a source overlay does **not**
  establish which driver is enabled on this specific model.

## Stage 28 next question

Check the filtered per-node `status` values and overlay fragments'
`target-path` or phandle-target presence without publishing the full
device tree or serial/identity properties. The offline script parses the
private local BOOT/DTBO images and prints a capped category-matched
subset of node paths.

```sh
cd ~/samsung-gtactive3LTE
python3 -m py_compile scripts/t575-stage28-fdt-status-targets.py
python3 scripts/t575-stage28-fdt-status-targets.py
```

The script never applies an overlay. Status shown for a base node or
an overlay node is **not** necessarily its effective merged status in
the running Android tree; `(inherited/default)` means no explicit
`status` property in that node, not a demonstrated active device.

This stage has no ADB connection, image extraction, write operations,
Download-mode handshake or flashing. BOOT/FLASH GATE: BLOCKED.
