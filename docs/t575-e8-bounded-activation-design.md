# SM-T575 audio E8: bounded PCM-triggered activation design

Status: DESIGN ONLY. Do not flash, install, or activate from this document.
Baseline: kernel 7.3.0; E4E activation locked; TAS2562 I2C 4-004c; SDZ gpm40-0 is gpiochip43 line 0 (GPIO descriptor named shutdown); PipeWire speaker PCM hw:0,1, S32_LE stereo 48 kHz.

## What has been verified
- E4D/E4F 500ms manually supervised pulse produced audible speaker audio with TAS2562 min gain and verified -45dB DVC coefficient.
- E5 ALSA trigger callbacks start/stop and close, amplifier OFF.
- E6 workqueue transitions start/stop, amplifier OFF.
- E7 delayed-work model: 500ms requested; observed expiry approximately 526ms after START, amplifier OFF throughout. It is NOT a hard deadline.
- E4E rollback restores shutdown GPIO LOW and allow_activation=N.
- /dev/watchdog0 is a 30s active S3C2410 system watchdog, not an audio amplifier cutoff. Do not interact with it.
- /sys/kernel/debug/gpio shows gpiochip43 gpm40 gpio-0 consumer shutdown out lo.

## E8 engineering requirements before any active hardware test
1. Isolate a new module source file/workflow; never overwrite the installed known-good E4E module.
2. Default deny activation; opt-in as a one-shot controlled test only, not a normal persistent PipeWire service.
3. Confirm known module hash, target kernel ABI, GPIO ownership and polarity, expected TAS2562 revision, clock validation, min gain, -45dB DVC readback, and fault/status registers before entering active mode.
4. Use the previously tested E4D 500ms pulse with 750ms emergency hrtimer as the active test base. The hrtimer drives SDZ LOW without sleeping; it is software and **not** an independent hardware protection circuit.
5. Ensure pulse begins only when a real PCM playback stream is running and stays bounded to one activation per module load; no automatic rearming or repeated retries. PCM stop/close must request immediate shutdown.
6. Harden stop/start/close synchronization. Atomic ALSA trigger callbacks cannot do sleeping I2C; a workqueue may. Avoid holding a mutex across cancellation or using a stack-backed timer that could race worker teardown.
7. Never leave the TAS2562 in active mode after an I2C readback failure, GPIO error, stream exit, suspend, module unbind, or SIGINT of test harness. Use independent GPIO-low assertions throughout and rollback to activation-locked E4E even on test failure.
8. Preserve PipeWire headset default and user-persistent t575_speaker; stop user audio services before replacing the module.
9. Verify hard-off in kernel pinctrl debug and debugfs GPIO, closed PCM, activation lock, and no reactivation after failed start.
10. Do not describe bounded E8 test as continuous-playback-safe. Determine a robust protection strategy for normal-length playback in a later stage, including physical/thermal amplifier fault behavior.

## Test execution sequence (to be implemented)
- Compile-only CI first, inspect artifacts and module metadata.
- Nonactivating integration test, two seconds of playback, verify event ordering and rollback.
- Review all cancellation/activation paths and signed-off test criteria.
- Only then supervised single 500ms audible diagnostic with controlled audio level and immediate fail-closed restoration.
- No default speaker routing or automatic desktop activation until downstream safety validation.

## Current status
E8 design gate only. No E8 candidate has been tested on hardware. SDZ must remain LOW.
