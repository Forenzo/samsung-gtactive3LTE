# Stage 41 — inspect the actual Linux audio source dependencies

## Owner-confirmed Stage 40 PASS

A static check against the existing T570 audio patch and generic kernel
config confirmed:

- Wi-Fi T570 speaker DAI CPU route uses `<&abox 1>`.
- Wi-Fi T570 speaker codec uses RT5510 (`<&rt5510>`).
- Samsung SM-T575 vendor Android tree links
  `/sound/uaif@1/codec` to TAS2562 DAI 0.
- The Linux T575 DTS intentionally disables inherited `/sound` and
  the wrong T570 RT5510 codec node.
- The generic bringup config still selects the Wi-Fi ASoC machine
  `CONFIG_SND_SOC_SAMSUNG_GTACTIVE3_RT5665=m`, not an LTE-specific
  machine driver. There is no TAS2562 codec config setting in it.

A PASS here is a **safe mismatch detection**, not proof of audio support.

## Stage 41 read-only source audit

The new `scripts/t575-stage41-asoc-source-dependencies.py` examines
public source files already in this repository, including `drv/audio`,
`patches/linux`, and `configs`. It reports files containing
TAS2562 driver/binding references, existing T570 ASoC machine symbols
and audio/UAIF1 route references. It also confirms that the LTE DTS
continues to disable the inherited sound card.

```sh
cd ~/samsung-gtactive3LTE
git pull origin port/sm-t575-bringup
python3 -m py_compile scripts/t575-stage41-asoc-source-dependencies.py
python3 scripts/t575-stage41-asoc-source-dependencies.py
```

This is a limited source-inventory test, **not** a kernel build and
not a dependency solver. In particular, a TAS2562 symbol appearing in
a patch does not establish that the packaged postmarketOS kernel patch
includes it or that the symbol will exist after the pinned kernel is
patched. If no source references are reported, a supported upstream
codec may still exist in the pinned kernel tree; that remains to
be verified against the exact checkout used by CI.

Do not copy the Wi-Fi RT5510 sound node onto LTE, or enable any
audio device until exact board machine binding, TAS2562 driver Kconfig,
power, clocks and I2S/ABOX DAI negotiation have been validated.

No tablet contact, device writes or source mutations. The
non-wiping recovery/first boot safety gate remains blocked.

**RESTORE/BOOT/FLASH GATE: BLOCKED.**
