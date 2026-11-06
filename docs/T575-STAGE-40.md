# Stage 40 — reconcile inherited T570 ABOX1 audio route with T575 TAS2562

## Stage 39 owner-confirmed PASS

The owner validated the stock SM-T575 merged BOOT + DTBO #5:
- `/sound/uaif@1/codec` references the TAS2562 codec's exact phandle.
- The `sound-dai` tuple has **two cells**: phandle plus one DAI specifier.
- DAI specifier is **0**.
- Earlier checks confirmed `compatible = "ti,tas2562"` among the
  codec compatibles, I2C address 0x4c, and `#sound-dai-cells = <1>`.
- Live Android reports TAS2562 `ok` and RT5510 `disabled`.

This establishes vendor DT linkage, not functioning Linux playback.

## Key finding from existing T570 Linux sources

The repository already has the upstream Wi-Fi audio patch
`patches/linux/0110-arm64-dts-exynos-gtactive3wifi-Add-audio.patch`.

Its `speaker-dai-link` **CPU** is `sound-dai = <&abox 1>`,
matching the UAIF1 path suggested by the T575 stock tree. Its
speaker **codec** is instead `sound-dai = <&rt5510>`, intended
for T570 board revision 4. The patch itself warns that board
revision 5+ uses TAS2562 instead.

Our LTE DTS correctly disables that inherited RT5510 node
and the inherited `/sound` node. Merely changing the codec
specifier to TAS2562 would be insufficient: the device-tree
binding, codec driver, ASoC card route, power/clock and audio
runtime dependencies require separate validation.

The repo's generic bringup config currently includes the
T570 ASoC machine symbol and MT6660/RT5510 rather than selecting
a TAS2562 codec. Do not change the common Wi-Fi config in place.

## Stage 40 audit

```sh
cd ~/samsung-gtactive3LTE
git pull origin port/sm-t575-bringup
python3 -m py_compile scripts/t575-stage40-wifi-lte-audio-topology.py
python3 scripts/t575-stage40-wifi-lte-audio-topology.py
```

The static check compares the public Wi-Fi patch, public LTE DTS
and generic kernel config. It does not use the private backups,
contact Android or build/enable hardware.

**A PASS only confirms that the current conservative isolation
is necessary and intact; it does not certify playable audio.**

Next: determine the actual TAS2562 ASoC codec driver Kconfig symbol
in the pinned kernel and the board's ABOX machine-driver requirements,
before drafting an LTE-only disabled prototype. Do not attempt a Linux
boot until non-wiping restoration and S-Boot display handover are proven.

**RESTORE/BOOT/FLASH GATE: BLOCKED.**
