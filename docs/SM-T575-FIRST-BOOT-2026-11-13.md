# SM-T575 first mainline Linux boot — 2026-11-13

## Status

**First confirmed Linux boot and interactive USB diagnostic console** on the owner's Samsung Galaxy Tab Active3 LTE **SM-T575**, using the fork's integration branch `integration/upstream-active3-family-firstboot`.

This was a **diagnostic-only BOOT partition experiment**, not a postmarketOS installation. Original rooted Android userdata and other partitions were not intentionally written. A **non-wiping recovery flash has not been independently demonstrated in this particular test**; keep the owner's verified rooted Android BOOT backup available.

### Build and image provenance

- CI run: [43447101392](https://github.com/Forenzo/samsung-gtactive3LTE/actions/runs/43447101392) — **success**, including LTE loader, ARM64 header and diagnostic ramdisk checks.
- LTE uniLoader SHA-256: `f3e6c5a78735df48e82173c2abfc9a6aa72056c6c8c9d71043d5997cdeebe17b`.
- Diagnostic ramdisk SHA-256: `5d21b8cefe195f0cd722a805f1f018cf566610be57ba77f884fa1864b0db4b55`.
- BOOT v2 diagnostic candidate SHA-256: `2c3981705053be7ae26289669b2e068ed66b830796b251117fbd188da715f0b2`, exactly **61,865,984 bytes**; original embedded T575 DTB byte-identical to rooted Android backup.
- Offline BOOT admission and recovery-controller `prepare` checks: **PASS** for image structure, hashes and PIT geometry. These checks do **not** verify AVB trust, runtime memory safety or S-Boot acceptance.
- Live Heimdall PIT reported 39 entries, with `BOOT` identifier 12, offset 27,792, block count 15,104.
- Initial transfer after an earlier `--no-reboot` PIT session printed “BOOT upload successful” but failed session-end acknowledgement, and Android retained its rooted BOOT hash. A later **fresh Download Mode** Heimdall BOOT-only transfer completed with “Rebooting device” and Linux booted.

### First boot — verified owner observations

- Kernel `Linux 7.3.0` ARM64, compiled on Ubuntu runner on 2026-11-13; `/proc/version` received over TCP diagnostic console.
- Display showed kernel and initramfs logs. Model property reads **Samsung Galaxy Tab Active3 LTE (SM-T575)**.
- Mac recognized a USB NCM network interface and connected successfully to the diagnostic IPv6 link-local console on TCP **23**. The greeting says “SM-T570” because it is a static string inherited from the common initramfs.
- Kernel uptime was **622.99 seconds** when queried.
- Memory: `MemTotal: 3761204 kB`, `MemAvailable: 3696040 kB` during diagnostic boot.
- UFS exposed `sda` through `sde`, with 31 visible `sda` partitions. `sda12` has 60,416 KiB (61,865,984 bytes), matching the BOOT backup geometry. Visibility alone is not a read/write integrity test.
- Battery `max170xx_battery`: capacity **52%**, `voltage_now=3837812` microvolts, `status=Charging`, `temp=185` (usually tenths of a degree Celsius, not independently validated). Charger `max77705-charger/status=Charging`.
- DRM: `/proc/fb` shows `0 exynosdrmfb`; `/sys/class/drm` includes `card0` and `card0-DSI-1`. Connector status **connected**, mode **1200x1920**. Backlight interface `16080000.backlight` present. Full native modeset, compositor and backlight control are **not yet tested**.
- Input: `/proc/bus/input/devices` lists **only gpio-keys**, `input0` / `event0`. Touchscreen and Wacom pen are **not yet enumerated** as input devices.

### Next engineering work

1. **Inspect modules and buses read-only.** Kernel config contains `CONFIG_TOUCHSCREEN_HIMAX_HX83112B=m` and `CONFIG_TOUCHSCREEN_WACOM_W9000=m`, but `initramfs/init.c` does not explicitly load either. Check `/lib/modules`, `/proc/modules`, SPI, I²C and DT presence first. Do not assume the HX83112B driver supports the T575 HX83102E touch hardware.
2. Review LTE DT peripheral routing, GPIOs, regulator and IRQ resources before attempting driver initialization. A module probe may write to hardware.
3. Test non-destructive UFS reads and battery telemetry consistency. Avoid mounting or modifying Android partitions.
4. Prepare a non-destructive full Linux userspace boot plan; don't install to Android userdata until recovery and basic peripherals are validated.
5. Keep cellular modem, EFS and sensitive partitions outside the first-boot experiments.

### Protection boundaries

Do not publish device-specific private dumps, serial numbers, firmware images or keys. No evidence in this report demonstrates full postmarketOS usability, modem functionality, Wi-Fi, touchscreen, S Pen, safe suspend, or a tested non-wiping restoration. The diagnostic BOOT image remains experimental.
