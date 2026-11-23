# SM-T575 E10 — Combined speaker and 3.5 mm headphone audio

## Verified baseline (2026-11-23)
- **RT5665 headphone jack** via A-Box UAIF0 ALSA PCM `hw:0,0`: owner confirms sustained video audio was audible in an earlier native-Linux test. Treat as WORKING; do not replace codec, mixer routes, PLL1, or the established speaker-independent headphone sink.
- **TAS2562 built-in speaker** via A-Box UAIF1 ALSA PCM `hw:0,1`: E9 successfully produced an audible 440 Hz tone using a PCM-triggered, 500 ms diagnostic pulse, with hardware shutdown GPIO GPM40-0 LOW after completion and E4E reinstalled with `allow_activation=N`. This does **not** establish safe long-duration speaker playback.
- **ASoC transport**: `drv/audio/t575/gtactive3lte_transport64.c` provides both distinct DAI links, with the RT5665 PLL derived from BCLK1 (sysclk = sample rate * 512). Preserve that.
- **UCM**: `pmos/aports/device/testing/samsung-gtactive3-common/ucm/HiFi.conf` is an existing RT5665/legacy RT5510 variant. The RT5510 `Digital` volume is invalid for the LTE TAS2562.
- **PipeWire**: `t575_speaker` ALSA sink built from `hw:0,1` at 48000 Hz, stereo, S32_LE; headset path `hw:0,0` remains the ordinary fallback sink. Do not create duplicate speaker sinks or change the default prematurely.

## E10 output goals
1. Keep RT5665 headphone output working continuously, with its already validated mixer path untouched.
2. Create a proper TAS2562 speaker state machine: stopped, preparing, active, stopping, latched fault.
3. Speaker on only after the DAI has an active PCM stream and the exact validated initialization, power, TDM-clock, low-gain and fault checks pass.
4. Hardware SDZ LOW on STOP, pause/suspend, PCM close, codec remove, fault, and failed initialization. Any in-flight I2C configuration must be prevented from re-enabling after a STOP; no I2C after SDZ goes LOW.
5. No unlimited speaker ON time until independent power cutoff or a sound bounded-session policy with verified rearm/stop synchronization is designed and tested. Existing software hrtimer is *not* an independent hardware watchdog.
6. Once the speaker driver is safe for actual playback: add UCM for `Speaker` (`hw:${CardId},1`) and `Headphones` (`hw:${CardId},0`); retain the RT5665 headphone controls without applying bogus RT5510 mixer volume.
7. Confirm headphone playback again **after** any combined UCM deployment; confirm speaker and headphone can be selected separately; verify no unintended simultaneous audio and preserve E4E rollback.

## Candidate UCM
- `pmos/aports/device/testing/samsung-gtactive3-common/ucm/HiFi-t575-e10-candidate.conf` preserves the existing headphone and mic mixer sequences and excludes legacy RT5510 speaker volume.
- It is a **candidate only**, not installed automatically. `JackControl` and `JackHWMute` reflect existing UCM; automatic switching needs a separate plug/unplug check.
- Deployment should occur only after sustained TAS2562 playback is demonstrably bounded and safe.

## Acceptance checks
- Playback using 3.5mm headphones continues to work with video and not just with a probe tone.
- At rest both hardware PCM devices are idle and GPM40-0 reads LOW.
- Headphone audio does not require enabling TAS2562.
- Speaker can play content beyond the original half-second pulse under a verified safety policy, and immediately returns to OFF at STOP.
- Headphones and speaker are independently selectable in Phosh/PipeWire and the appropriate default policy is confirmed.
