# SM-T575 Stage 36 — TAS2562 upstream binding gap inventory

## Previous stage

The owner reran the Stage 34 LTE DTS safety audit after Stage 35 CI
integration and confirmed all checks **PASS**. The Linux DTS remains
intentionally conservative: T570 RT5510 and sound disabled, DECON-F
takeover disabled, LTE reserved memory and bootloader framebuffer
protected, SPI touchscreen 7 MHz cap preserved.

Stage 35 changed the GitHub workflow to enforce the static safety
audit. **No successful GitHub Actions build is independently confirmed.**

## Concrete Linux driver target

Current mainline Linux includes an ASoC TAS2562 codec driver:
- https://github.com/torvalds/linux/blob/master/sound/soc/codecs/tas2562.c
- https://www.kernel.org/doc/Documentation/devicetree/bindings/sound/ti,tas2562.yaml

The matching Linux driver recognizes `compatible = "ti,tas2562"`.
The upstream binding specifies additional properties for codec setup
and connection; Samsung's proprietary DT may use different names and
does not by itself guarantee mainline compatibility.

The user's SM-T575 Android merged FDT has `tas2562@4c` with
`status=ok`, and the runtime live Android FDT confirmed the same
status via Magisk read-only inspection. The RT5510 at 0x34 is disabled.
This validates stock device topology; it is *not* evidence that the
upstream Exynos ASoC machine driver supports this route.

## Stage 36 — private offline property-name report

```sh
cd ~/samsung-gtactive3LTE
git pull origin port/sm-t575-bringup
python3 -m py_compile scripts/t575-stage36-tas2562-binding-inventory.py
python3 scripts/t575-stage36-tas2562-binding-inventory.py
```

The script reads the verified local BOOT+DTBO backups from
`~/Downloads/SM-T575-Recovery`, merges overlay #5 privately via
`fdtoverlay`, then outputs presence/absence of a fixed list of
potentially relevant TAS2562 properties. It does not print raw DT
property values, extract/upload private files, contact Android,
modify kernel DTS, or flash anything.

The property-name inventory will let us distinguish vendor-only
configuration from what the upstream binding can express before
proposing a *disabled-by-default* Linux codec node.

The upstream Linux driver existing is not sufficient to enable audio;
supplies, reset/IRQ pins, I2C controller mapping, `#sound-dai-cells`,
Exynos ABOX clocking and ASoC card topology remain to be validated.

**RESTORE/BOOT/FLASH GATE: BLOCKED.**
