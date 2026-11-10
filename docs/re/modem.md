# Modem: the Exynos 9810's Shannon CP (Galaxy Tab Active3 LTE, SM-T575)

Facts for a mainline modem driver, 2026-11-11. Nothing built or run, no firmware touched or
decompiled: everything here is read from Samsung's GPL kernel for the same SoC, public
reverse-engineering projects and three recent out-of-tree efforts, and written in our own words.
The driver outline is `patches/linux/0154` (`drivers/remoteproc/samsung_shannon_cp.c`, not
enabled anywhere); the variant itself: [../VARIANTS.md](../VARIANTS.md).

Markers: **[V]** VERIFIED (read in the source named, path:line) · **[R]** REPORTED (a third party
says so; not re-checked) · **[?]** UNKNOWN / needs a measurement or an owner decision.

Source shorthands (all public, read 2026-11-11):

| Short | What | URL |
|---|---|---|
| GPL | LineageOS `android_kernel_samsung_universal9810`, branch `lineage-17.1`, commit `5a2dd7d6` (Galaxy S9/S9+/Note9, Exynos 9810, kernel 4.9). Same `modem_v1`/`mcu_ipc`/`cal-if` code family as the Tab Active3 4.9.191 kernel | https://github.com/LineageOS/android_kernel_samsung_universal9810/blob/lineage-17.1/ |
| GIST | T. Garnock-Jones, free `cbd` re-implementation for Galaxy S7 (Exynos 8890, same `modem_v1`) | https://gist.github.com/tonyg/4ea14f4dfe414422c0648c6e0a8bcb5d (`qnd_cbd.py`) |
| LSI | libsamsung-ipc (Replicant, GPL-2.0+), fork `manoedinata/libsamsung-ipc` with `herolte` + 2026-10 Shannon LTE commit | https://github.com/manoedinata/libsamsung-ipc |
| SSTIC | Berard & Fargues (Synacktiv), "How to design a baseband debugger", SSTIC 2020, Galaxy S7 | https://www.sstic.org/media/SSTIC2020/SSTIC-actes/how_to_design_a_baseband_debugger/SSTIC2020-Article-how_to_design_a_baseband_debugger-berard_fargues.pdf |
| FW | FirmWire (BSD-3), Shannon emulator; `S360AP` = the 9810 CP | https://github.com/FirmWire/FirmWire |
| ZTOS | Zerone-Laboratories/ztOS (GPL-3): Galaxy S9 on Arch Linux ARM + 7.1 kernel, modem booted 2026-10-12 | https://github.com/Zerone-Laboratories/ztOS/blob/main/modem/README.md |
| HAKI | Scion-Project/scion-starlte PR #25 `docs/modem-plan.md` (S9 under XNU; docs only, merged 2026-11-02) | https://github.com/Scion-Project/scion-starlte/pull/25 |
| OMA | derekross/linux-omarchy-mobile PR #144 (Google cpif for gs201) + derekross/omarchy-mobile `device/{cheetah,raven}/MODEM-PLAN.md` | https://github.com/derekross/linux-omarchy-mobile/pull/144 |
| ML | torvalds/linux master, read 2026-11-11 | https://github.com/torvalds/linux |

Caveat on the device: the owner's tablet is the **Wi-Fi SM-T570** ([HARDWARE.md](../../HARDWARE.md)).
Everything below is for the **LTE SM-T575**. The T575's stock DT values (Forenzo's live FDT: `modem_if` 0xF0000000 +
0x09200000, `cp_ram_logging` 0xF9200000 + 0x02000000, `mif_pdata` compatible
`sec_modem,modem_pdata`) are byte-identical to the S9's `exynos9810-rmem.dtsi:26-34` and
`modem-ss360ap-sipc-pdata.dtsi:14-18` [V], so the S9 GPL tree is a valid reference. Whether a
T575 is available for tests: **[?]**.

---

## 0. Short answer

- The CP is a Cortex-R7 class core inside the SoC (CP "ss360ap", FirmWire `S360AP`, chip id
  0x0360_0000 [V FW `firmwire/vendor/shannon/soc/__init__.py:70-84`]). It has no bus of its own:
  it shares DRAM (146 MB at 0xF0000000) and talks to the AP through a 16-interrupt / 64-register
  mailbox block (`MCU_IPC` at 0x14170000). Power and reset are PMU registers, two of which
  (`CP_CTRL_S/NS`) are **secure** and reachable only through SMC 0x82000700. The firmware is
  signed; EL3 verifies it on another SMC (same ID, mode 0). Everything the AP needs to do is in
  GPL code; nothing in the DT is secret.
- The CP has no flash: its NV data (`nv_data.bin`, IMEI + calibration) lives in the **EFS**
  partition and is **uploaded into CP RAM** by `cbd` at every boot, and the running CP later reads
  and **writes** files on EFS through the RFS channel (served by `rild` on stock). Our rules forbid
  writing EFS and even reading identity partitions with our scripts. **A modem that works needs an
  owner decision on reading `nv_data.bin`**; writes can be kept in RAM (what ZTOS/HAKI/OMA all do).
- Precedent: ZTOS booted this exact CP on a 7.1 kernel (S9) by porting Samsung's `modem_v1` as an
  out-of-tree module and running the **vendor `cbd` in a chroot**: SIM read, network registered,
  SMS sent (2026-10-12) [R ZTOS]. Nobody has a free RIL for the 9810's IPC dialect; ZTOS got status
  queries through Samsung IPC and the rest through **AT commands on `/dev/umts_router`** [R ZTOS].
- Honest estimate: a bring-up (vendor-style driver as a module + vendor `cbd` + AT/ModemManager
  experiments) is 3-6 weeks with a T575 on USB; a mainline-shaped driver (remoteproc + mailbox +
  wwan) is 3-6 engineer-months; a free, complete RIL (calls, data, SMS) for this CP is the open
  research problem (many months, with captures of the stock RIL's traffic, allowed only as facts in
  `docs/re/`).

---

## 1. Architecture (stock, and what we would build)

```
            stock Android (SM-T575)                      mainline target
 ┌──────────────────────────────────┐     ┌──────────────────────────────────────────┐
 │ rild + libsec-ril.so (prop.)     │     │ ModemManager / oFono  ◀── D-Bus          │
 │  ├─ Samsung IPC on umts_ipc0     │     │   ▲ (A) generic AT on wwan0at0 (router)  │
 │  ├─ RFS server (NV, /efs files)  │     │   │ (B) libsamsung-ipc daemon + MM bridge │
 │  └─ PDP ctx -> rmnetN            │     │ cp-helper: TOC from RADIO (ro), NV RAM   │
 │ cbd (prop.): TOC, XMIT_BOOT, SMC │     │   copy, RFS server (RAM overlay, no EFS  │
 └───────────┬──────────────────────┘     │   writes)                                │
             │ /dev/umts_boot0/ipc0/rfs0  └───────────┬──────────────────────────────┘
             │ ioctl + read/write, rmnetN            │ remoteproc (fw load, start/stop,
 ┌───────────▼──────────────────────┐     ┌───────────▼───────────── coredump)        │
 │ drivers/misc/modem_v1 (GPL)      │     │ shannon-cp (new): PMU seq via syscon,    │
 │  modem_main/io_device: iodevs    │     │  SMC 0x82000700, AP2CP_CFG, boot/dump     │
 │  modem_ctrl_ss310ap: power/boot  │     │ shannon-sipc link: 4 MB legacy map +      │
 │  link_device_shmem + sbd: rings  │     │  SBD rings, SIPC5 framing, CMD handshake  │
 │ drivers/misc/mcu_ipc (mailbox,   │     │  -> wwan core: ports (SIPC/AT/RFS) +      │
 │  shm_ipc reserved mem)           │     │     netdevs (raw IP, like iosm/t7xx)      │
 │ drivers/soc/samsung/cal-if       │     │ exynos-mailbox (extended: 9810 mcu_ipc     │
 │  (pmucal_cp), exynos-smc         │     │  variant) + syscon for the ISSR registers  │
 └───────────┬──────────────────────┘     └───────────┬──────────────────────────────┘
             │ MCU_IPC 0x14170000 (SPI 69)            │
             │ PMU 0x14060000 (+SMC for CP_CTRL_*)    │
             │ DRAM 0xF0000000..0xF91FFFFF (shared)   │
 ┌───────────▼─────────────────────────────────────────▼──────────────────────────────┐
 │ Shannon CP (S360AP): BOOT @+0, MAIN @+0x10000, VSS, NV, IPC region @+0x8000000 (5 MB),│
 │ ZMB @+0x8500000 (11 MB); CP view of shared mem = 0x48000000 (FW)                     │
 └────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. The kernel driver stack in Samsung's tree (what to read, what it reads)

All [V] GPL unless marked.

| Piece | Files | Role | DT / registers it reads |
|---|---|---|---|
| Core + io devices | `drivers/misc/modem_v1/modem_main.c`, `modem_io_device.c`, `modem_v1.h`, `modem_prj.h` | builds 21 "iodevs" (misc char devs `umts_*`, netdevs `rmnetN`) from DT; ioctls `_IO('o', …)` | `mif_pdata`: `mif,name/modem_net/modem_type/ipc_version/link_types/link_name/link_attrs/num_iodevs/buff_offset/buff_size` (`modem_main.c:278-292`), mailbox indices `mbx_*`, `mif,int_ap2cp_*`, `mif,irq_cp2ap_*`, `sbi_*` (`:478-533`), children `iodevs/io_device_N` with `iod,name/id/format/io_type/links/attrs/…` (`:556-579`) |
| CP control | `modem_ctrl_ss310ap.c` | power, reset, boot on/off, crash/dump, CP_FAIL/CP_WDT IRQs, mailbox status bits | `interrupts` index 0 = `cp_fail` (`:749-760`), index 1 = `cp_wdt` (`:766-778`); GPIOs for HW rev (`:165-190`), `modem_ctrl,gpio_cp_rst_n` optional (`:806`) |
| Link device | `link_device_shmem.c` (3921 lines), `link_device_memory.h`, `link_device_memory_sbd.c`, `include/sbd.h`, `include/sipc5.h` | the shared-memory IPC: legacy 4 MB map, SBD rings, SIPC5 framing, command handshake, boot/dump copy, `IOCTL_SECURITY_REQ` | `shm_get_*()` from `shm_ipc`; mailbox irqs `irq_cp2ap_msg/status/perf_req_*/wakelock/ratmode/smapper` (`:3750-3880`); `platform_get_resource(…, IORESOURCE_MEM, 0)` = `mif_pdata reg` = main-binary offset 0x10000 (`:3886`, dtsi `:16`) |
| Shared memory | `drivers/misc/mcu_ipc/shm_ipc.c`, `include/linux/shm_ipc.h` | takes the reserved regions, maps boot/IPC/ZMB/VSS/cplog, computes SMC params | `RESERVEDMEM_OF_DECLARE("exynos,modem_if")` (`shm_ipc.c:459-469`), `"exynos,cp_ram_logging"` (`:472-483`); node `samsung,exynos-shm_ipc`: `shmem,cp_size/vss_size/ipc_offset/ipc_size/zmb_offset/zmb_size` (`:620-660`) **unless** a valid CP memory map is found in the image at `base+0x200+0xA0` (`:568-619`) |
| Mailbox | `drivers/misc/mcu_ipc/mcu_ipc.c`, `regs-mcu_ipc.h`, `include/linux/mcu_ipc.h` | 16 AP→CP and 16 CP→AP interrupts, 64 shared 32-bit registers | `samsung,exynos-shd-ipc-mailbox` (`mcu_ipc.c:528-533`), `reg`, one IRQ, `mcu,id`, `mcu,name`, `mcu,irq_affinity_mask` (`:434-471`, `:376`) |
| PMU / secure | `drivers/soc/samsung/pmu-cp.c`, `include/soc/samsung/pmu-cp.h`, `drivers/soc/samsung/cal-if/pmucal_cp.c`, `cal-if/exynos9810/pmucal_cp_exynos9810.h` | CP power/reset sequences; `CP_CTRL_S/NS` through SMC when `CONFIG_CP_SECURE_BOOT` | PMU base 0x14060000 (hard-coded in the CAL tables) |

### 2.1 Device-tree facts (S9 tree; the T575 identical where measured)

- `reserved-memory/modem_if`: `exynos,modem_if`, `<0 0xF0000000 0x9200000>` (146 MB, no `no-map`)
  [V `exynos9810-rmem.dtsi:26-29`]; `cp_ram_logging`: `<0 0xF9200000 0x2000000>` [V `:31-34`];
  cplog is used only when the cmdline has `androidboot.cp_reserved_mem=on` [V `shm_ipc.c:502-510`].
- `mif_pdata` [V `modem-ss360ap-sipc-pdata.dtsi:14-110`]: `reg = <0 0x10000 0>` ("modem main
  binary start offset"), `interrupts = <0 74 0>, <0 440 0>` (= `INTREQ__ALIVE_CP_ACTIVE` 74 →
  cp_fail, `INTREQ__CP2AP_WAKEUP` 440 → cp_wdt [V `include/dt-bindings/interrupt-controller/exynos9810.h:91,462` + `modem_ctrl_ss310ap.c:749,766`]),
  `mif,name "ss360ap"`, `modem_type 10` (SEC_SS310AP), `ipc_version 50` (SIPC 5.0),
  `link_types 0x200` (SHMEM), `link_attrs 0x7C9` = XMIT_BTDLR|DUMP_ALIGNED|BOOT_ALIGNED|MEM_DUMP|
  MEM_BOOT|DPRAM_MAGIC|SBD_IPC, `num_iodevs 21`, `buff_offset 0x500000`, `buff_size 0x900000`.
  Mailbox register indices: `ap2cp_msg 0, cp2ap_msg 1, ap2cp_united_status 2, cp2ap_united_status 3,
  ap2cp_mif_value 4, cp2ap_dvfsreq_cpu/mif/int 5/6/7, ap2cp_kerneltime 9`. Interrupt indices:
  ap2cp `msg 0, wakeup 1, status 2, active 3, smapper 4`; cp2ap `msg 0, status 2, active 3,
  smapper 4, perf_req cpu/mif/int 5/6/7, wakelock 8, ratmode 9`. Status-bit fields (`sbi_*`):
  `cp_status` mask 0xF pos 1, `lte_active` bit 5, `cp_wakelock` bit 6, `cp_rat_mode` 6 bits at 26,
  `ap_status` mask 0xF pos 1, `pda_active` bit 5, `sys_rev` 8 bits at 6, `ds_det` 2 bits at 14,
  `ext_backtrace` bit 17, `device_type` 5 bits at 18, `crash_type` 4 bits at 23.
- `shmem` node [V `:377-386`]: `cp_size 0x7900000` (121 MB), `vss_size 0x700000` (7 MB),
  `ipc_offset 0x8000000`, `ipc_size 0x500000` (5 MB), `zmb_offset 0x8500000`, `zmb_size 0xB00000`.
- `mailbox_cp: mcu_ipc@14170000` [V `exynos9810-starlte_common.dtsi:945-952`]:
  `samsung,exynos-shd-ipc-mailbox`, `reg <0 0x14170000 0x180>`, `interrupts <0 69 0>`
  (`INTREQ__MAILBOX_CP2AP` [V `exynos9810.h:86`]), `mcu,id 0`.
- Board-level `mif_pdata` adds 8 GPIOs (CP_REV0-3, AP_REV0-3 on gpg3/gpg1) [V `starlte_common.dtsi:958-965`]
  — the T575's pins: **[?]** (read from the T575 stock DT).
- The 21 iodevs [V `:112-374`]: `umts_ipc0/1` ch 235/236 FMT ("RIL"), `umts_rfs0` ch 245 RFS,
  `umts_boot0` ch 215 BOOT ("CBD"), `umts_ramdump0` ch 225 DUMP, `rmnet0..7` ch 10..17 RAW
  `io_type 1` (NET) attrs 0x180 (SBD_IPC|NO_LINK_HDR), `multipdp`/`multipdp_hiprio` ch 0
  MULTI_RAW (dummy demux; `multipdp` attrs 0x3180 adds SMAPPER|ZEROCOPY), `umts_csd` 1,
  `umts_router` 25 ("Data Router"), `umts_dm0` 28 (DIAG), `umts_cass` 35, `smd4` 33, `umts_ciq0` 26.

### 2.2 Mailbox block (MCU_IPC) [V `regs-mcu_ipc.h:18-55`, `mcu_ipc.c`]

| Offset | Name | Use |
|---|---|---|
| 0x00 | MCUCTLR | bit 0 = software reset of the block (`mbox_sw_reset`, `mcu_ipc.c:301-310`) |
| 0x08/0x0C/0x10/0x14/0x18 | INTGR0/INTCR0/INTMR0/INTSR0/INTMSR0 | CP→AP: pending bits 16..31 in INTSR0 (`mcu_ipc_handler :49-86` masks `0xFFFF0000`), cleared by writing INTCR0 |
| 0x1C/0x20/0x24/0x28/0x2C | INTGR1/INTCR1/INTMR1/INTSR1/INTMSR1 | AP→CP: `mbox_set_interrupt(n)` writes `1<<n` to INTGR1 (`:238-243`) |
| 0x80 + 4·n (n < 64) | ISSR0.. | shared 32-bit registers = "mailboxes" (`mbox_set_value :266-269`, `MAX_MBOX_NUM 64`, `include/linux/mcu_ipc.h:34`) |

Mainline already has `drivers/mailbox/exynos-mailbox.c` for the ACPM mailbox (gs101 / exynos850):
same register family but **different offsets** (INTGR0 0x8, INTMR1 0x24, INTGR1 0x40, INTMR0 0x28)
[V ML `drivers/mailbox/exynos-mailbox.c:19-33,132-136`; binding `google,gs101-mbox.yaml`]. A 9810
`mcu_ipc` variant (INTGR1 0x1C, INTMR0 0x10, 16 channels each way) is a small addition. The ISSR
"value" registers do not fit the mailbox framework's message model; expose them as a `syscon`
regmap the modem driver uses directly.

### 2.3 PMU registers and SMC IDs [V `include/soc/samsung/pmu-cp.h:55-155`]

- `CP_CTRL_NS 0x0030`, `CP_CTRL_S 0x0034`, `CP_STAT 0x0038`, `CP_DEBUG 0x003C`;
  `CENTRAL_SEQ_CP_CONFIGURATION 0x0280`, `CENTRAL_SEQ_CP_STATUS 0x0284` (status byte at bits 23:16),
  `RESET_SEQUENCER_STATUS 0x0504` (bits 2:0; 0x5 = CP running), `RESET_AHEAD_CP_SYS_PWR_REG 0x1320`,
  `CLEANY_BUS_CP_SYS_PWR_REG 0x1324`, `LOGIC_RESET_CP_SYS_PWR_REG 0x1328`, `TCXO_GATE_SYS_PWR_REG 0x132C`,
  `CP_DISABLE_ISO_SYS_PWR_REG 0x1330`, `RESET_ISO_SYS_PWR_REG 0x1334`, `CLEANY_BUS_CP_CONFIGURATION 0x3920`,
  `CLEANY_BUS_CP_STATUS 0x3924`, `CP2AP_MEM_CONFIG0..2 0x7200-0x7208`, `CP2AP_ADDR_RNG 0x720C`,
  `CP_ADDR_CFG0..14 0x7140-0x7178`.
- `CP_CTRL_NS` bits: `CP_PWRON` 1, `CP_RESET_SET` 2, `CP_ACTIVE_REQ_EN/CLR` 5/6, `CP_RESET_REQ_EN/CLR`
  7/8, `MASK_CP_PWRDN_DONE` 9, `SWEEPER_BYPASS_DATA_EN` 16, `WDT_FLAG` 20; `CP_CTRL_S`: `CP_START` bit 3.
- **SMC 0x82000700** (`SMC_ID`), `READ_CTRL 3`, `WRITE_CTRL 4`; `enum cp_control { CP_CTRL_S = 0,
  CP_CTRL_NS = 1 }`. Read = two SMCs (arg2 = 0 low half, 1 high half; result status in low 16 bits,
  value in the high 16) [V `pmu-cp.c:16-56`]. The same SMC ID with `mode` 0/1/2 as arg1 is the
  **secure-boot request** (section 3). `SMC_ID_CLK 0x82001011` with 0/1 = SSS clock enable/disable
  around it [V `modem_v1.h:31-33`].
- 9810 PMUCAL sequences [V `pmucal_cp_exynos9810.h:2-40`]: `cp_init` = CP_CTRL_NS |= bit1, CP_CTRL_S
  |= bit3, delay, wait `RESET_SEQUENCER_STATUS & 7 == 5`, wait GIC `0x10101238 bit 28` pending;
  `cp_status` = `RESET_SEQUENCER_STATUS & 7` (5 = up); `cp_reset_assert` = the seven `*_SYS_PWR_REG`
  writes (0x1320..0x1338), CP_CTRL_NS |= bit2, CENTRAL_SEQ_CP_CONFIGURATION bit16 = 0, wait
  CENTRAL_SEQ_CP_STATUS[23:16] == 0x80; `cp_reset_release` = CP_CTRL_S |= bit3, wait status == 0,
  wait GIC pending bit 28. The LineageOS-24 S9 kernel builds with `CONFIG_CP_PMUCAL=y` [R HAKI §8.1].
- On the 9810, `modem_on` does **not** run the PMU sequence itself: it writes bit 0 (`AP2CP_CFG_DONE`)
  of **`AP2CP_CFG` at 0x14820000** ("CP_INIT, AP_BAAW setting is executed in el3_mon when coldboot.
  If AP2CP_CFG is set, then CP_CPU will work") [V `modem_ctrl_ss310ap.c:307-351`]; `cal_cp_init()`
  is run once from the security request if `cal_cp_status()==0` [V `link_device_shmem.c:2289-2295`].

---

## 3. CP boot sequence (facts, in order)

Who: `cbd` (proprietary, `/vendor/bin/cbd -d -tss310 -bm -mm -P platform/11120000.ufs/by-name/RADIO`
[R HAKI §8.2, from a LineageOS-24 S9 vendor image]; on the Tab the UFS address differs **[?]**) reads
`modem.bin` from the **RADIO** partition and `nv_data.bin` from **EFS**, and drives `/dev/umts_boot0`.

**TOC** (first 512 bytes of RADIO): 16 entries of 32 bytes: `char name[12]; u32 offset; u32
loadaddr; u32 size; u32 crc; u32 entryid` [V FW `TOCFile.py:83-87`; V GIST `qnd_cbd.py:37,84-86`];
entries `TOC, BOOT, MAIN, (VSS), NV, (OFFSET)`; ZTOS saw "BOOT, MAIN, VSS, NV" on the S9 [R].
`shm_ipc` also reads a `MEMn` memory-map table at `base + 0x200 + 0xA0` of the loaded image with
`IPC/VSS/VPA/ZMC/LOG` entries that override the DT sizes [V `shm_ipc.c:515-619`]; ZTOS: "CP memory
map verification: PASS (5 binaries)" [R].

| # | Step | Side | Source |
|---|---|---|---|
| 0 | EL3 (S-Boot's monitor) programs the CP's address window (BAAW) and CP_INIT at cold boot | EL3 | [V comment `modem_ctrl_ss310ap.c:337-339`] |
| 1 | open `umts_boot0`; `IOCTL_MODEM_RESET` (0x6f21) | cbd→kernel | [V GIST:96; `modem_prj.h:76`] |
| 2 | `IOCTL_SECURITY_REQ` (0x6f53) `{mode 2 (CP_BOOT_RE_INIT), 0, 0}` → SMC 0x82000700(2, 0, 0) | cbd→kernel→EL3 | [V GIST:106; `link_device_shmem.c:2263-2304`; `shm_ipc.c:280-324`] (cbd `setuid(1001)` first; as root the SMC returned 11 = CP_NOT_WORKING, which cbd ignores [R GIST:98-105]) |
| 3 | `IOCTL_MODEM_XMIT_BOOT` (0x6f40) with `struct modem_firmware {u64 binary; u32 size, m_offset, b_offset, mode, len}` for BOOT, MAIN, then NV (from `/efs/nv_data.bin`), chunks ≤ 62 KiB, `m_offset = entry.loadaddr - BOOT.loadaddr`, mode 0. Kernel `copy_from_user` to `boot_base + m_offset` (mode 0) or the IPC region (mode 1 = dump), bounds-checked | cbd→kernel | [V GIST:62-112; `link_device_shmem.c:2172-2226`; `modem_prj.h:176-183`] |
| 4 | `IOCTL_SECURITY_REQ {mode 0, size_boot, size_main}` → SSS clk on (SMC 0x82001011,0), `cal_cp_init()` once, SMC 0x82000700(mode \| phys_base if memory-map in use, bl_size, main_size), SSS clk off. EL3 marks BOOT+MAIN secure, verifies the signatures, configures the CP with 0xF0000000 as its main memory. Error codes 0..20 (`CP_NO_ERROR … CP_CORRUPTED_CP_MEM_INFO`) | kernel+EL3 | [V `link_device_shmem.c:2277-2300,142-164`; R SSTIC §3.4 (GS7, BOOT at 0xF0000000, MAIN at +0x10000)] |
| 5 | `IOCTL_MODEM_ON` (0x6f19): clear the 64 mailbox regs, write sys_rev/ds_det/cplog flag into `ap2cp_united_status`, set `pda_active`, write `AP2CP_CFG` bit 0, sleep 300 ms | kernel | [V `modem_ctrl_ss310ap.c:252-382`] |
| 6 | `IOCTL_MODEM_BOOT_ON` (0x6f22): `ld->boot_on` sets `MEM_BOOT_MAGIC` 0x424F4F54 in the IPC map; poll `cp_status` field of `cp2ap_united_status` != 0 (100 × 10-20 ms); enable CP_FAIL irq | kernel | [V `:487-520`; `link_device_shmem.c:2141-2170,2426-2458`; magic `link_device_memory.h:535-538`] |
| 7 | `IOCTL_MODEM_DL_START` (0x6f28); then on the boot channel: write u32 0x900d → read 0xa00d, write 0x9f00 → read 0xaf00 (frames go through the legacy NORM_RAW queue, `xmit_udl`) | cbd↔CP bootloader | [V GIST:118-123; LSI `herolte.c:305-362`; `link_device_shmem.c:1323-1357`]; the 9810 values **[?]** (ZTOS: "the boot handshake passes" with vendor cbd [R]) |
| 8 | CP raises mailbox irq `cp2ap_msg` with value `MASK_CMD_VALID\|CMD_INIT_START` (0x41): AP builds the SBD descriptors (`init_sbd_link`) and answers `CMD_PIF_INIT_DONE` (0xD) | kernel | [V `link_device_shmem.c:441-486`; codes `link_device_memory.h:122-151`] |
| 9 | CP → `CMD_PHONE_START` (0x8): AP resets the IPC map (`MEM_IPC_MAGIC 0xAA`, access 1) and answers `CMD_INIT_END` (0x2) **only if both `umts_ipc0` and `umts_rfs0` are open** (`rild_ready`), else when they are opened later (`shmem_init_comm`); link state → IPC, `init_cmpl` completed | kernel, gated on user space | [V `:561-650,412-439,2015-2076`] |
| 10 | `IOCTL_MODEM_BOOT_OFF` (0x6f23) waits `init_cmpl` (timeout → -EAGAIN), enables CP_WDT irq, iodevs → ONLINE; `IOCTL_MODEM_BOOT_DONE` is a no-op | kernel | [V `modem_ctrl_ss310ap.c:522-559`] |
| 11 | rild opens `umts_ipc0`/`umts_rfs0`; RFS requests start at once | RIL | [R HAKI §8.4] |

Crash path: CP → `CMD_CRASH_RESET` / `CMD_CRASH_EXIT`; AP sets `MEM_CRASH_MAGIC 0xDEADDEAD`,
cbd collects a dump through `umts_ramdump0` (`IOCTL_MODEM_DUMP_START`, mode 1 security request puts
the dump in the IPC region) [V `:297-410,652-689`; `shm_ipc.c:288-293`]. AP→CP doorbell: value in
`ISSR[ap2cp_msg]`, then INTGR1 bit `int_ap2cp_msg` [V `:2586-2598`].

---

## 4. IPC framing

- **SIPC5 link header** [V `include/sipc5.h:22-61`]: byte 0 `cfg`: bits 7:3 = 0b11111 start mark;
  bit 2 PADDING, bit 1 EXT_FIELD, bit 0 CTL (bits 1:0 == 0b11 multi-frame, 0b10 extended length);
  byte 1 channel id; bytes 2-3 length (LE, header included); optional byte 4 control (multi-frame
  `more` bit 7 + 7-bit id [V `modem_prj.h:205-209`]) or bytes 4-5 extended length → header 4/5/6
  bytes; padding to 8 bytes when `aligned`. Reserved channels 0, 5, 6, 27, 255 [V `modem_prj.h:226-231`].
- **Channel map** [V `modem_v1.h:125-208`]: RAW 1-4 CS/VT, 7 CDMA, 8 PCM, 9 screen, **PDP 10-24**
  (`rmnetN` = 10+N), 25 BT_DUN (`umts_router`), 26 CIQ, 28/29 CPLOG, 30/31 loopback, 35 CASS,
  **BOOT 215-224, DUMP 225-234, FMT 235-244, RFS 245-254**.
- **FMT payload (Samsung IPC)** [V `modem_prj.h:211-218`]: `u16 len; u8 msg_seq; u8 ack_seq; u8
  main_cmd; u8 sub_cmd; u8 cmd_type;` then data. Groups/commands as in libsamsung-ipc
  `include/*.h` (PWR, CALL, SMS, SEC, NET, MISC, SVC, SS, GPRS, SAT, CFG, IMEI, GEN, RFS) [R LSI];
  the 9810 firmware rejects some SIPC4-era layouts (SMS, raw SIM) with `GEN_PHONE_RES` 0x8001
  [R ZTOS `ril/zrn-ril.py`]. The complete 9810 message set exists only inside `libsec-ril.so`
  (`IpcProtocol41`) **[?]** — to be learnt by capture/decompile, recorded as facts in `docs/re/`.
- **Transport** [V]: legacy 4 MB map `struct shmem_4mb_phys_map` at the IPC region: `magic, access`,
  FMT tx/rx head/tail, RAW tx/rx head/tail, 4056 B reserved (ECT clock table), FMT buffers 4 KiB each,
  RAW tx 2084864 B, RAW rx 2 MiB [V `link_device_memory.h:63-116`]; with `SBD_IPC` set the data
  path is **SBD rings**: ctrl region 1 KiB, cmd 1 KiB, descriptors up to 64 KiB, buffers after
  (`sbd.h:60-72`), per channel `sbd_rb_channel {ul_rbd_offset, ul_sbdv_offset, dl_rbd_offset,
  dl_sbdv_offset}` and `sbd_rb_desc` (ch, direction, length, id, buff_size, payload_offset),
  `sbd_global_desc {version=1, num_channels, rbps_offset}` with rp/wp arrays [V `sbd.h:87-168`,
  `link_device_memory_sbd.c:239-259,991`]. ZTOS: "the CP sets up 9 SBD ring buffers" [R].
  Doorbell mask bits: `MASK_SEND_FMT 0x2`, `MASK_SEND_RAW 0x1`, `REQ_ACK_FMT/RAW 0x20/0x10`,
  `RES_ACK_FMT/RAW 0x8/0x4`, `CMD_VALID 0x40`, `INT_VALID 0x80` [V `link_device_memory.h:122-135`].
- **IP data**: `rmnetN` are `ARPHRD_PPP`, `IFF_POINTOPOINT|IFF_NOARP`, `hard_header_len 0`, MTU
  1500 [V `modem_io_device.c:1372-1377`]; with `ATTR_NO_LINK_HDR` frames are raw IPv4/IPv6 in the
  ring, protocol chosen from the IP version on rx [V `:320-358,1239-1250`]. The RIL binds a PDP
  context to a channel over FMT (GPRS group); on newer Shannon firmware the attach also needs
  `IPC_NET_SERVICE_DOMAIN_CONFIG` (CS+PS) and `IPC_GPRS_LTE_ATTACH_APN_INFO` 0x0D14 [R LSI commit
  2026-10-15, measured on an Exynos 7570 Galaxy J4].

---

## 5. RFS: what the CP needs from EFS

- The CP has no storage. `nv_data.bin` (per-device: IMEI, calibration) is **uploaded into CP RAM**
  at the `NV` TOC entry's load address by cbd at every boot [V GIST:111-112; LSI `herolte.c:274`].
- At run time the CP issues RFS requests on ch 245: item-level `RFS_NV_READ_ITEM`,
  `RFS_NV_WRITE_ITEM`, `WRITE_ALL_ITEM`, `BUFFER_MESSAGE`, `RESTORE` and file-level `OPEN/CLOSE/
  READ/WRITE/LSEEK/GET_FILE_INFO/FTRUNCATE/CREATE/UNLINK/RENAME/PUT/GET/MAKE_DIR/REMOVE_DIR/
  OPEN_DIR/READ_DIR/CLOSE_DIR`; the server is a thread **inside rild** (`ril-rfs`,
  `Nv::ProcessRfsMessage`), roots `/mnt/vendor/efs` and `/mnt/vendor/cpefs`; rild writes
  `/efs/nv_data.bin`, its `.md5` and backup; SELinux gives cbd **read-only** EFS access; CPEFS is
  mounted `ro,noload` [R HAKI §8.2-8.4, LineageOS-24 S9 vendor image]. Item ids
  `IPC_RFS_NV_READ_ITEM 0x4201`, `NV_WRITE_ITEM 0x4202` [R LSI `include/rfs.h`].
- The kernel driver does nothing with EFS itself; it only gates `INIT_END` on `umts_rfs0` being
  open [V `rild_ready`]. Without an RFS server the CP never gets `INIT_END` (stock driver), or
  gets it and then stalls on its first NV read **[?]**.
- **Policy fit.** Our rules: EFS is never written (`installer.protected`), identity partitions are
  never read by our snapshot scripts (`NEVER_READ`). The three recent efforts all chose: read a
  copy of `nv_data.bin` once (owner's own backup, outside git), serve RFS from a **RAM overlay**,
  accept writes into RAM, never flush [R HAKI §2; R OMA cheetah/raven "NV only as verified RAM
  copies"; ZTOS mounted EFS rw for vendor cbd — not acceptable here]. **Owner decision needed**:
  (a) allow a one-time read of `efs:nv_data.bin` (and the RFS file roots) into RAM at boot, by the
  helper on the device, never leaving it; or (b) no modem. Reading RADIO is not an identity read.

---

## 6. Userspace options (ranked by feasibility)

| Rank | Option | State | Sources |
|---|---|---|---|
| 1 | **Vendor `cbd` in a minimal Android chroot** (reads RADIO, boots the CP) + our RFS stub | proven on this CP under a 7.1 kernel (ZTOS, 2026-10-12) and on Pixel 6/7 cpif (OMA, with vendor `cbd`+`rfsd`) | [R ZTOS README "Step 2 and 3"; R OMA cheetah §8] |
| 1b | **Free cbd**: ~150 lines (GIST) / LSI `herolte_boot()`; same ioctls on `umts_boot0`; needs the 9810's boot-channel handshake values confirmed | GPL code exists for the 8890; 9810 untested with it | [V GIST; V LSI `herolte.c:243-372`] |
| 2 | **AT commands on `umts_router` (ch 25)** → `+CPIN`, `+COPS`, `+CREG`, `+CGREG`, `+CSQ`, PDU-mode SMS send work; text-mode SMS fails; voice/data via AT **[?]** | reported on the S9 | [R ZTOS `ril/at.py`, `send-sms.py`] — exposes a path to **ModemManager generic AT** if the channel becomes a `WWAN_PORT_AT`; whether a PDP activated by AT lands on `rmnetN` is **[?]** (OMA on the S5300: AT query on `umts_router` got no reply [R cheetah §6]) |
| 3 | **libsamsung-ipc-based daemon** (GPL-2.0+): `herolte` profile boots a `modem_v1` CP and speaks SIPC over `umts_ipc0`/`umts_rfs0` with the SIPC4-era FMT ops; a 2026-10 fork adds the LTE attach messages (Exynos 7570). Needs a 9810 device profile + dialect fixes (0x8001 rejections) + ModemManager/oFono glue. oFono patches exist only in `xc-racer99/ofono` (`plugins/samsung*.c`, last 2019-07-20) and build only against libsamsung-ipc 1.x [R pmbootstrap #598]. ModemManager has **no** Samsung-IPC plugin [R; listing could not be fetched] | partial, needs RE of the 9810 dialect | [V LSI tree; R ZTOS] |
| 4 | **Own daemon + fake ModemManager D-Bus** (the OMA model: `sitd` speaks the modem's protocol, `omamobile-mmd` owns `org.freedesktop.ModemManager1` so GNOME Calls/Chatty/NetworkManager work) | works on Pixel 6/7 (SIT protocol, not SIPC) — architecture reusable, protocol not | [R OMA cheetah "T0/T1", raven status 2026-10-27] |
| 5 | **Vendor `rild` + `libsec-ril` via libhybris / ofono-binder (Halium way)** | needs binder in our kernel and a HIDL client; no Exynos-S9 Halium/UBports/Droidian port found (the Droidian S9 is the Snapdragon `starqlte`) | [R UBports forum; ZTOS "rild needs binder"] |
| — | Replicant/libsamsung-ipc mainline XMM626x SIPC driver (`net: add Samsung IPC interface driver`) | different modem (HSIC XMM), never merged; Replicant wiki pages are behind a bot wall today | [R search snippets only] |

Reverse-engineering resources (facts only, per `.claude/rules/firmware.md`): FirmWire (BSD-3)
models `S360AP` (`SIPC_BASE 0x8F170000`, `SHM_BASE 0x48000000` = the CP's view of 0xF0000000, boot
peripheral 0x95B40000) and parses the TOC, but documents neither the AP-side FMT messages nor
the S9's handshake [V FW `soc/__init__.py:70-84`]; `grant-h/ShannonBaseband` (MIT): Ghidra loader
for `modem.bin`, BTL (CP RAM log) parsers [V README]; `Comsecuris/shannonRE`: TOC 010 template,
`unpack_modem.py`, ramdump collection via cbd [V README]; SSTIC 2020 describes the boot and that
64 mailboxes exist with ~20 used [R SSTIC §3.3-3.4].

---

## 7. Mainline-shaped driver sketch

Nothing Samsung-modem-shaped is in mainline: `drivers/net/wwan` has iosm, t7xx, mhi, qcom_bam_dmux,
rpmsg only; no Samsung remoteproc; `exynos9810.dtsi`/`exynos9810-starlte.dts` carry only the PMU
syscon and a framebuffer reservation [V ML tree listing, 2026-11-11].

**Components and the subsystem to reuse**

1. `exynos-mailbox` variant for `MCU_IPC` (16 doorbells each way; `samsung,exynos9810-mcu-ipc`
   compatible; the ISSR block as a child `syscon`). Reuse: `drivers/mailbox/exynos-mailbox.c`.
2. `exynos-cp-pmu` helper: the PMUCAL sequences on the PMU `syscon` + the two SMC-only registers via
   `arm_smccc_smc(0x82000700, …)`; `AP2CP_CFG` 0x14820000. Reuse: `syscon`, `arm_smccc`.
3. `shannon-rproc` (remoteproc): `prepare` = security request mode 2; `load` = copy BOOT/MAIN/NV
   into `memory-region` (the ELF loader does not fit: a custom `load`/`parse_fw` for the TOC);
   `start` = security request mode 0 + modem_on + boot_on + boot-channel handshake; `stop`;
   `coredump` = the DUMP channel. Firmware delivery: `request_firmware` cannot read a block device,
   so a small helper assembles `shannon-cp.bin` (= RADIO's TOC + BOOT + MAIN) and `shannon-nv.bin`
   into `/run/firmware` and uses the firmware **uevent fallback** or a sysfs `firmware_name`
   attribute; the NV blob never persists outside RAM.
4. `shannon-sipc` link (the bulk): IPC-region map, SBD rings, SIPC5 mux/demux, command handshake
   gated on **the RFS server being up** (not on a RIL). Registers with `drivers/net/wwan`:
   `wwan_create_port()` for FMT (needs a new `WWAN_PORT_SIPC`, or `WWAN_PORT_UNKNOWN`-style raw
   port), RFS, BOOT/DUMP (or keep those on the rproc), and `WWAN_PORT_AT` for ch 25; netdevs through
   `wwan_register_ops` + link ids = PDP channels (the iosm/t7xx pattern). The umts_* char-dev ABI is
   not mainlinable; the vendor daemons need it, hence the staging below.
5. Power: CP2AP_WAKEUP (SPI 440) and the mailbox are wake sources; the CP asks for MIF/INT/CPU
   DVFS through mailboxes 5-7 (acknowledge and ignore at first [R ZTOS]); `cp_call` sleep mode in the
   PMU wakeup config [V `exynos9810.dtsi:446-447`].

**DT binding sketch** (board T575; names to be agreed upstream; `exynos9810-gtactive3.dts` reserves the two regions today)

```dts
reserved-memory {
	cp_mem: modem@f0000000 { reg = <0x0 0xf0000000 0x0 0x9200000>; no-map; };   /* ioremap_wc, not linear map */
	cp_log: modem-log@f9200000 { reg = <0x0 0xf9200000 0x0 0x2000000>; no-map; }; /* optional */
};
mbox_cp: mailbox@14170000 {
	compatible = "samsung,exynos9810-mcu-ipc";
	reg = <0x14170000 0x180>;
	interrupts = <GIC_SPI 69 IRQ_TYPE_LEVEL_HIGH>;
	#mbox-cells = <1>;                     /* 0..15 = AP->CP doorbells (INTGR1 bits) */
	cp_mbox_regs: syscon@80 { compatible = "syscon"; reg = <0x80 0x100>; };  /* ISSR0..63 */
};
modem@14820000 {
	compatible = "samsung,exynos9810-shannon-cp";
	reg = <0x14820000 0x4>;                /* AP2CP_CFG */
	samsung,pmu-syscon = <&pmu_system_controller>;
	samsung,mbox-regs = <&cp_mbox_regs>;
	memory-region = <&cp_mem>, <&cp_log>;
	mboxes = <&mbox_cp 0>, <&mbox_cp 1>, <&mbox_cp 2>, <&mbox_cp 3>;
	mbox-names = "msg", "wakeup", "status", "active";
	interrupts-extended = <&gic GIC_SPI 74 IRQ_TYPE_LEVEL_HIGH>,   /* cp_fail  (ALIVE_CP_ACTIVE) */
	                      <&gic GIC_SPI 440 IRQ_TYPE_LEVEL_HIGH>,  /* cp_wdt   (CP2AP_WAKEUP)    */
	                      <&mbox_cp 0>, <&mbox_cp 2>, <&mbox_cp 3>, <&mbox_cp 8>, <&mbox_cp 9>; /* cp2ap msg/status/active/wakelock/ratmode */
	samsung,cp-layout = <0x7900000 0x700000 0x8000000 0x500000 0x8500000 0xb00000>; /* cp, vss, ipc off/size, zmb off/size; overridden by the image's MEMn table */
	samsung,main-offset = <0x10000>;
	samsung,buff-region = <0x500000 0x900000>;
	wakeup-source;
};
```
The channel table (21 iodevs, sbi bit positions) is firmware ABI, not board data: keep it in the
driver keyed by compatible, not in DT (upstream reviewers will refuse the `iodevs` tree).

**Staging plan** (the sketch in `patches/linux/0154` is the start of P3's shape; P1 comes first on a real T575)

| Phase | What | Effort (one engineer, T575 on USB) | Risk |
|---|---|---|---|
| P1 bring-up | Port `mcu_ipc` + `shm_ipc` + `modem_v1` as one out-of-tree module on our kernel (ZTOS did it on 7.1 in days: compat header, PMUCAL sequences, SMC via `arm_smccc`, `ioremap_wc` for the no-map region, zero-copy off); DT overlay with the stock nodes; vendor `cbd` in a chroot from the owner's own firmware; RFS stub in RAM. Goal: CP ONLINE, `umts_ipc0` answers, AT on `umts_router` | 3-6 weeks | medium: SMC 0x82000700 under our boot chain (S-Boot's EL3 stays, so expected OK as on ZTOS); EFS read policy; a CP that dies at `INIT_END` without a real RFS answer |
| P2 userspace | Free cbd (GIST/LSI); ModemManager via AT port for registration/SMS; data path test (`rmnet0` after AT `+CGACT`, or SIPC GPRS messages from LSI) | 4-8 weeks | high: the 9810 FMT dialect is undocumented; voice needs ABOX/VSS audio paths |
| P3 mainline shape | remoteproc + mailbox + wwan driver as above, binding doc, upstream review | 3-6 months | medium: `WWAN_PORT_SIPC` acceptance; firmware-from-partition model |

**Risks and unknowns, listed**

- Hardware availability: a **T575** is needed; the T570 has no CP (its `modem_if` reservation is a
  question for the stock DT) **[?]**.
- EFS: reading `nv_data.bin` is unavoidable for a working CP; writing must stay in RAM. A corrupt
  or missing NV makes the CP "NV rebuilding" (`CMD_NV_REBUILDING` 0xB [V]) and can touch IMEI
  state **[?]** — never test with the real EFS mounted rw.
- Secure boot: EL3 refuses unsigned or mismatched images (`CP_WRONG_BL_SIZE`, `CP_NOT_VALID_MAGIC`
  …); the image **must** come from the owner's own stock firmware of the same build as EFS/CPEFS
  expect **[?]** (version coupling between modem.bin and NV is reported for other Samsungs).
- Memory: 146 MB + 32 MB reserved on a 3.6 GB tablet; the region must be `no-map` and mapped
  write-combined (ZTOS fixed two linear-map bugs [R]).
- Power: the CP wakes the AP (SPI 440, mailbox); suspend with the CP up needs the `cp_call`
  mode and DVFS/QoS handling (ZTOS commits 2026-10-20 "the CP mailbox wakes the AP from system
  sleep", 2026-10-30 "sleep resets" [R]).
- Voice: audio runs CP ↔ ABOX (VSS 7 MB image, calliope); VoLTE/IMS is a RIL-level stack nobody
  free has for Shannon; 2G/3G shutdowns make CS calls unreliable [R OMA raven "VoLTE: the network
  refuses the IMS bearer"].
- Licensing: `modem_v1` is GPL-2.0 (portable with attribution); libsamsung-ipc GPL-2.0+; vendor
  `cbd`/`libsec-ril` proprietary (run from the owner's firmware only, never shipped); FirmWire
  BSD-3, ShannonBaseband MIT (facts only).

---

## 8. Open questions for the owner / next measurements

1. Is an SM-T575 available? Which firmware build (modem.bin and EFS must match)?
2. May the helper read `efs:nv_data.bin` (and the RFS roots) into RAM at boot, never written back?
   (Extends `NEVER_READ` semantics: a device-local read by the modem helper, not by our scripts.)
3. From the T575 stock DT: `mif_pdata` GPIOs, the UFS by-name path of RADIO, any `cp_ram_logging`
   cmdline, the `shmem` values — confirm they equal the S9's.
4. From a rooted stock T575 (read-only, owner's yes): `dmesg` lines `mif`/`shmem`/`cbd` ("CP memory
   map", `CP_NO_ERROR`), the boot-channel handshake values, `logcat -b radio`.
