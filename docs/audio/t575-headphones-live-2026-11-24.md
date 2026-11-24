# SM-T575 LTE native Linux: RT5665 headphone audio recovery (2026-11-24)

> **Status: proven live on one SM-T575; boot autostart and TAS2562 speaker not validated.**
> This is a reproducibility record of the known-good configuration and test evidence.
> The captured runtime scripts were published as privacy-redacted templates with checksums; boot autostart is still untested.
> **Do not enable the internal speaker or flash a boot image using these instructions.**

## Proven result

On a Samsung Galaxy Tab Active3 LTE **SM-T575**, running Nura edge / postmarketOS-derived Linux with kernel **7.3.0**, the following were observed on 2026-11-24:

- The **patched RT5665** codec and SM-T575 machine driver played normal audio from LibreWolf through a wired headset. Sound and volume changes were normal for the 30-second and two-minute sessions.
- The normal system-wide PipeWire/WirePlumber path then worked continuously with the managed service, and the user confirmed audible sound.
- The HiFi UCM profile was selected automatically: `Active Profile: HiFi`, `Default Sink: alsa_output.platform-sound.HiFi__Headphones__sink`.
- Stopping the managed service restored the original codec/card. Starting it again restored the correct headphone sink. A second test after moving controller files to protected storage also passed.
- The TAS2562 activation gate was verified **`N`** before and after live tests; speaker audio remains **unimplemented/unverified**.
- The final running system service uses protected `/etc/t575-headphones/headphones-managed.sh` and `rollback-v2.sh`, and **remains disabled at boot**. The permanent UCM extension was installed under `/var/lib/extensions/t575-headphones`; a reboot has **not** yet confirmed its boot-time behavior.

Do not conflate a discovered ALSA/PipeWire sink with audible output. The codec patch and route initialization are also required. Do not assume suspend/display-blank behavior has been established by short tests. The system's true suspend action was disabled in the observed journal.

## Tested hardware and environment

| Item | Confirmed value |
| --- | --- |
| Machine | Samsung Galaxy Tab Active3 LTE, SM-T575, Exynos 9810 |
| OS | Nura `edge`, `ID=nura`, `SYSEXT_LEVEL=26111790` |
| Kernel | `7.3.0 SMP preempt mod_unload aarch64` |
| Root | `/dev/mapper/root`, ext4, read-write |
| `/usr` | `/dev/mapper/usr`, EROFS, read-only |
| ALSA | card `0` / ID `Active3` / driver `snd_soc_gtactive3lte_transport64` |
| Headphone PCM | `hw:0,0`, Headset `rt5665-aif1_1-0` |
| Speaker PCM | `hw:0,1`, TAS2562 safeactive, **do not use** |
| RT5665 | I2C `3-001b` |
| TAS2562 | I2C `4-004c` (amplifier safety locked) |
| Stock codec | `/lib/modules/7.3.0/kernel/sound/soc/codecs/snd-soc-rt5665.ko.zst` |
| Verified patched module | SHA256 `792866896625a515557116768b108f3e26dfc9997928fa1777720557d8d83907` |
| PipeWire | `1.6.11` as reported by `wpctl status` |
| systemd | `262 (262.2)` |
| systemd-sysext | enabled/active; on first boot runs about 11s after startup |
| User audio | `pipewire.socket` and `pipewire-pulse.socket` enabled; WirePlumber enabled; user linger `no` |

The patch, pinned kernel source, and experimental compilation entry point already exist in this branch:

- [RT5665 calibration-recovery patch](../../patches/audio/t575/rt5665-calibration-recovery.patch) — introduced in commit `0ecdd997741c96b98f9f6712a7361a27b794cbc4`.
- [Audio build workflow](../../.github/workflows/t575-audio-unified.yml) — applies the patch to the kernel and builds an experimental codec module.
- [External audio module build script](../../scripts/t575-stage98-build-audio-modules.sh) — requires a matching kernel source/config and `Module.symvers`/toolchain.
- [SM-T575 machine-driver candidate](../../drv/audio/t575/gtactive3lte_unified_candidate.c) — experimental; **not** a validated TAS2562 activation path.

**Rebuild caveat:** the module's original SHA256 is a known-good reference, not a guarantee that a new build will be byte-identical. Check `uname -r`, `modinfo -F vermagic`, kernel configuration, exported symbol versions, and runtime safety before loading. The CI workflow itself warns that compilation does not certify loadability against the running kernel.

## Why this codec fix is necessary

The stock RT5665 was silent during PCM playback even though the ALSA card and playback pointer could run. The successful experimental patch repairs regmap cache state after headphone/mono calibration timeout: after codec reset, it calls `regcache_mark_dirty()` then `regcache_sync()` before marking calibration done. Logs may still say `HP Calibration Failure` despite successful audio.

During verified headset playback at 48 kHz, stereo S16LE, observed:

```text
BCLK = 1536000 Hz
SYSCLK = 24576000 Hz
RT5665 080: 4100
RT5665 081: 1701
RT5665 082: 0800
```

These are observations, **not** instructions to force-write registers.

## Headphone-only UCM and system extension

The headphone-only UCM profile reconstructed from our successful bring-up is kept in [`packaging/t575-headphones/sysext/`](../../packaging/t575-headphones/sysext/). The full UCM files have **not yet been compared byte-for-byte** with the protected running tablet's version; verify before claiming an exact source snapshot.

- `usr/lib/extension-release.d/extension-release.t575-headphones`: `ID=nura`, `SYSEXT_LEVEL=26111790`.
- `usr/share/alsa/ucm2/conf.d/Galaxy_Tab_Acti/Galaxy_Tab_Acti.conf`: `Syntax 6`, HiFi use case.
- `usr/share/alsa/ucm2/conf.d/Galaxy_Tab_Acti/HiFi.conf`: RT5665 headphone mixer route, `PlaybackPCM "hw:${CardId},0"`, jack control `Headset Jack`. There is **no speaker device**.

For a *fresh test device*, first check its OS extension level, codec safety, and system-extension support. Installing an extension can change running ALSA discovery. Reproduce the tested process in a controlled environment:

```sh
# Run locally on the tablet; requires a clone of this branch.
test "$(grep '^SYSEXT_LEVEL=' /etc/os-release)" = 'SYSEXT_LEVEL=26111790'
test -d packaging/t575-headphones/sysext
sudo test ! -e /var/lib/extensions/t575-headphones
sudo install -d -m 0755 /var/lib/extensions
sudo cp -a packaging/t575-headphones/sysext /var/lib/extensions/t575-headphones
sudo systemd-sysext merge
systemd-sysext status
alsaucm -c hw:0 list _verbs
alsaucm -c hw:0 list _devices/HiFi
```

On the tested device the UCM was first staged in `$HOME`, then copied to `/run/extensions/t575-headphones` and merged **without rebooting**; after validation, it was copied to `/var/lib/extensions/t575-headphones` for persistence. After restarting **only** WirePlumber, `auto_null` briefly appeared; approximately five seconds later the real HiFi headphone sink appeared. The running service continued to use the user PipeWire/Pulse sockets, and Phosh was not stopped.

**Important:** the codec starts probing around boot timestamp **4s**, whereas `systemd-sysext.service` starts around **11s**. Overlaying a patched codec in `/usr` does **not** replace a codec already loaded into kernel memory. We deliberately did **not** overlay `snd-soc-rt5665.ko.zst`: doing so could break the stock-codec `modprobe` rollback path.

## Controlled driver switch (reproduce from exact controller sources)

The successful runtime controller was developed by adapting a short experimental switch. Key operations, guarded by speaker-lock and kernel ABI checks:

1. Check `/sys/module/t575_tas2562_safeactive/parameters/allow_activation` is **`N`**; verify the patched module's checksum/ABI, ALSA card, bindings, and available recovery script.
2. Keep `pipewire.service` and `pipewire-pulse.service` running. Stop **only** `wireplumber.service` to release ALSA. Stopping PipeWire/Pulse previously caused a Phosh volume UI crash/logout.
3. Unbind `sound` from `/sys/bus/platform/drivers/gtactive3lte-transport64`, and `3-001b` from `/sys/bus/i2c/drivers/rt5665`. Unload the stock `snd_soc_rt5665`; load the verified patched module; rebind codec, then card.
4. Allow approximately **3s** after the codec probe for asynchronous calibration to settle; initialize/check `Stereo1 DAC MIXL DAC L1` and `Stereo1 DAC MIXR DAC R1` on, `HPO` on, and conservative `Headphone` mixer gain (verified test 5/15; later managed test 3/15).
5. Restart WirePlumber and wait for `alsa_output.platform-sound.HiFi__Headphones__sink`; select that sink, unmute it, and use a conservative application volume (~20%). All ordinary app audio then uses PipeWire.
6. On managed service stop or an error, restore **the original codec** using the verified rollback procedure; verify card and I2C binding, restart needed user audio services, and ensure speaker lock remains `N`.

The protected working files on the tested tablet are:

```text
/etc/t575-headphones/headphones-managed.sh
/etc/t575-headphones/rollback-v2.sh
/etc/t575-headphones/snd-soc-rt5665.ko
/etc/t575-headphones/headphone-tone-quiet.pcm
/etc/t575-headphones/t575-headphones.service
/etc/systemd/system/t575-headphones.service
```

The final service was root-owned, mode `0700` for the containing directory; the `*.ko` was mode `0600`. The service unit's `ExecStart` and `ExecStopPost` paths were verified as `/etc/t575-headphones/...`. See [the reference unit](../../packaging/t575-headphones/t575-headphones.service).

The **privacy-redacted versions of validated protected runtime scripts** and systemd unit are archived in [`packaging/t575-headphones/tested-runtime/`](../../packaging/t575-headphones/tested-runtime/) with [SHA256SUMS](../../packaging/t575-headphones/tested-runtime/SHA256SUMS). The original uploaded scripts were inspected and redacted before public publication. These GitHub templates **are not byte-identical to the originals**: the personal account name and numeric user runtime paths were replaced with `__AUDIO_LOGIN__` and `__AUDIO_UID__` placeholders. The driver sequence is retained, but the templates **must be personalized and safety-tested locally**. They still pin the verified kernel and codec module checksum. The [read-only capture helper](../../scripts/t575-capture-headphone-runtime.sh) can export a fresh runtime snapshot without stopping audio. The `.ko` remains a separately compiled binary and is not committed; rebuild from the existing source patch and validate ABI and runtime safety.

## Verified recovery and commands

To stop the **currently installed service** and restore the original codec:

```sh
sudo systemctl stop t575-headphones.service
sudo systemctl status t575-headphones.service --no-pager
cat /proc/asound/cards
```

To start it again **on the verified device with its protected scripts already installed**:

```sh
sudo systemctl start t575-headphones.service
sudo systemctl is-active t575-headphones.service
pactl info | grep 'Default Sink'
pactl list short sinks
```

The stop/start/recovery test passed on 2026-11-24. An old 90s independent rollback timer protected *short experiments*, but the final continuous service has **no short timeout/watchdog**; recovery relies on the controller's EXIT/signal trap and systemd's `ExecStopPost`. Those mechanisms cannot promise recovery after a kernel hang, sudden power loss, or failed root filesystem.

The service was intentionally left **disabled** for autostart (`systemctl is-enabled t575-headphones.service` reported `disabled`). User login has `Linger=no`; system PipeWire sockets are active in the user session. Before enabling boot startup, implement/check bounded waits for `user@__AUDIO_UID__.service`, user PipeWire sockets, and WirePlumber; validate extension merge order, safety module readiness, and boot recovery. No reboot validation has been performed yet.

## Read-only verification checklist

```sh
uname -r
cat /proc/asound/cards
aplay -l
modinfo -n snd_soc_rt5665
sudo modinfo -F vermagic /etc/t575-headphones/snd-soc-rt5665.ko
sudo sha256sum /etc/t575-headphones/snd-soc-rt5665.ko
sudo cat /sys/module/t575_tas2562_safeactive/parameters/allow_activation  # MUST be N
systemd-sysext status
alsaucm -c hw:0 list _verbs
pactl list short cards
pactl info | grep 'Default Sink'
systemctl --user is-active pipewire pipewire-pulse wireplumber
sudo systemctl is-active t575-headphones.service
sudo systemctl is-enabled t575-headphones.service
```

Be mindful that the sysfs safety parameter generally needs root to read. `SUSPENDED` on an idle PipeWire sink is normal; it is not a proof of audio failure.

## Unfinished work

- Verify that the committed UCM reference files match the tablet's live staged UCM byte-for-byte; document the final binary build provenance (compiler/config/Module.symvers).
- Make headphone service boot-ready with bounded user-session waits, preserve original-codec rollback, test reboot and display off/on behavior.
- Verify jack insert/removal, microphone input, audio across more applications, and volume UI regressions.
- Investigate TAS2562 speaker separately **without changing `allow_activation=N`** until hardware safety/protection is validated.
- Eventually incorporate the RT5665 recovery patch and independently validated speaker driver into the production kernel, using the shared machine driver and a full routing UCM.

### Security and safety

Do **not** commit private passwords, tokens, SSH endpoints, personal logs, stock firmware, raw dumps, or device-unique boot images. Do not replace `/usr` EROFS, boot firmware, initramfs, or the stock codec as part of reproducing the headphone test. The archived source patch is **experimental**, not an upstream-approved or production-certified fix.

## Redacted runtime template hashes (November 24, 2026)

These **redacted** archives derive from the tested uploaded files with identifying login and UID strings replaced. Hashes below identify the **published sanitized copies**, not the private originals. They must be personalized locally before execution. **Do not enable the unit on boot without additional startup readiness and recovery testing.**

| Archived file | SHA256 |
| --- | --- |
| `headphones-managed.sh` | `3cecd7227ebdfa6fd1e923f7a1908f13fc40cccd9348942833108b69ba502531` |
| `rollback-v2.sh` | `1a9ffb7a3b02af8858fcf2e12edd9ea45ad4f2274943bc96b6c2b2780acf8a1d` |
| `t575-headphones.service` | `de6769d40f9d9d938fdc313f2ea58722889121f26460fc8e13df0edf926f185d` |

```sh
cd packaging/t575-headphones/tested-runtime
sha256sum -c SHA256SUMS
```

**Implementation review:** `rollback-v2.sh` restores the original module only when `/run/t575-rt5665-test.active` exists. The managed controller creates that marker, uses an EXIT/signal trap for cleanup, and the unit adds `ExecStopPost`. Recovery was validated in normal stop/restart tests, but is **not a failsafe** against a hung kernel, a corrupt marker, an unavailable root filesystem, a mismatched module, or other abnormal failures. The final managed controller contains an intentional infinite sleeping loop to stay alive until stopped; later code after the loop is unreachable during normal execution. Do not assume this demonstrates a boot-ready health check or hardware speaker safety beyond the explicitly verified `allow_activation=N` gate.

### Personalizing private account placeholders

The archived scripts and service unit **cannot be run without substitution** by design. Locally replace `__AUDIO_LOGIN__` with the target's Phosh/PipeWire login and `__AUDIO_UID__` with the result of `id -u` for that login. Do not commit the rendered files. See the [redacted runtime README](../../packaging/t575-headphones/tested-runtime/README.md) for an offline example.

The tablet's installed and working root-owned scripts were not changed by this public-repository privacy cleanup.
