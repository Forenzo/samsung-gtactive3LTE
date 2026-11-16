# SM-T575 Mali-G72: Exynos9810 G3D power-domain dependency (hardware evidence)

**Status: source investigation only; no kernel fix accepted; no flash approved.**

## Physical SM-T575 results (2026-11-17)

Under the experimental NFS Linux 7.3.0 diagnostic kernel:

- The Exynos DPU/KMS driver initializes and exposes `/dev/dri/card0` and `card0-DSI-1` at 1200×1920.
- Panfrost and gpu-sched modules load, but no `renderD128` render node appears.
- `/sys/bus/platform/drivers/panfrost` contains only `uevent`, `bind`, `unbind`, `module`: no bound device.
- `/sys/bus/platform/devices` has `17500000.gpu`.
- `/sys/kernel/debug/devices_deferred`: `17500000.gpu platform: supplier 14064040.power-domain not ready`.
- Live DT supplier `/soc@0/power-domain@14064040` has a **single** compatible string:
  `samsung,exynos9810-g3d-pd`; sysfs modalias:
  `of:Npower-domainT(null)Csamsung,exynos9810-g3d-pd`.

The successful read-only NFS mount and Wacom/Himax input driver initialization are independent of this GPU issue.

## Why generic Exynos genpd options alone are not a fix

The upstream `drivers/pmdomain/samsung/exynos-pm-domains.c`
match table currently recognizes `samsung,exynos4210-pd`
and `samsung,exynos5433-pd`, **not**
`samsung,exynos9810-g3d-pd`.

References:
- https://codebrowser.dev/linux/linux/drivers/pmdomain/samsung/exynos-pm-domains.c.html
- https://www.cateee.net/lkddb/web-lkddb/EXYNOS_PM_DOMAINS.html

Turning on `CONFIG_PM_GENERIC_DOMAINS=y` and
`CONFIG_EXYNOS_PM_DOMAINS=y` without implementing a compatible driver
is thus *not established* to resolve this supplier. Do **not** simply
append this custom compatible string to the generic driver's OF match
table: register layout, secure-monitor access, voltage, timing, reset,
and clock ordering might differ, and undocumented writes could damage
stability or interrupt recovery.

The early draft config-only change in this PR was reversed immediately
after the live DT compatible was inspected. No device changes were made.

## Next engineering gates

1. Locate and inspect the exact Linux kernel patch sources used in the
   NFS BOOT build, including SoC DT and the `17500000.gpu` node.
2. Identify the intended Exynos9810-specific G3D power-domain provider;
   check `14064040` base, register size, reset/clock dependencies,
   regulator and secure-monitor requirements against proven source.
3. If source support already exists behind another Kconfig option,
   enable it **only** in an opt-in build and confirm the fully generated
   kernel configuration and compiled-driver OF match table.
4. Otherwise implement an Exynos9810-specific reviewed provider,
   with hardware-safe access and explicit power-sequencing tests,
   **without** forcing binds or bypassing `-EPROBE_DEFER`.
5. Compile and audit the new kernel offline. Preserve current NFS
   BOOT image and the known-good Android BOOT backup. Any hardware
   trial requires a separate explicit approval and recovery gate.
6. Once a safe provider is running, inspect deferred probes and
   `/dev/dri/renderD128` before attempting Weston or Plasma Mobile.

No changes to device runtime, BOOT, DTBO, Android internal storage,
NFS server or network are requested by this investigation.
