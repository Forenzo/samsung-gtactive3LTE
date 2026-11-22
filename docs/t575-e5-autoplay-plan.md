# SM-T575 E5 automatic speaker playback — staged bring-up

Status: development only. **Not approved for on-device installation.**

## Evidence obtained

- Kernel 7.3.0 native Linux, ASoC card 0, speaker PCM hw:0,1, 48 kHz stereo S32_LE.
- TAS2562 on I2C 4-004c; shutdown GPM40, pin 16.
- Two bounded -60 dB pulses and one bounded -45 dB pulse produced audible sound.
- -45 dB coefficient: 00 5c 22 4e; hardware gain stays at documented minimum.
- E4F script proved a 500 ms supervised activation with 750 ms watchdog and attempted E4E rollback.
- The locked E4E module remains the on-device baseline. Verify pin LOW and allow_activation=N after every test.

## Safe design order

1. **E5 lifecycle-only candidate (current)**: model ALSA DAI callbacks; log START/STOP/CLOSE, never power amplifier; compile-only CI. Do not install this unreviewed candidate.
2. Validate real callback ordering and that every error/unplug/stream close/suspend path has a shutdown event; inspect how PipeWire suspends idle PCM.
3. Implement a process-context workqueue/state machine for hardware transitions. DAI trigger must not sleep or issue I2C; do not raise SDZ in trigger callback.
4. Add explicit OFF/ARMING/ACTIVE/STOPPING/FAULT states, concurrency serialization, fault latch, no automatic fault retries, verified clocks and DVC/gain at each enable, runtime suspend and removal shutdown, immediate GPIO low on faults.
5. Hard-cap continuous activation during initial tests, with independent safe-off mechanism and no replay after watchdog expiry. Ensure no new module can remain powered on STOP/CLOSE/SUSPEND/underrun.
6. Start at -45 dB and minimum hardware gain; implement volume as capped ALSA mixer control after protection behavior is verified. Do not present a 0–100% user-facing slider until hardware bounds are validated.
7. After on-device gated tests pass, configure PipeWire/WirePlumber default speaker route, test notifications/music, and confirm idle power draw. Do not make it boot-persistent until safe recovery is demonstrated.

## Important limitation

Existing one-shot hrtimer and software rollback are not hardware safety certification. They do not establish safe continuous speaker operation, thermal limits, or speaker-specific voltage/current limits. No unattended or indefinite activation should be attempted from this stage.
