# SM-T575 Stage B amplifier detection

Date: 2026-11-21
Kernel: 7.3.0 #27-postmarketOS
Build commit: 48a5b89d
Workflow run: 44902664950

## Results

- TAS2562 instantiated on I2C bus 4, address 0x4c.
- Detection-only external module loaded successfully.
- Initial power register: 0x0e.
- Silicon revision register: 0x10.
- Shutdown register write and readback: 0x0e.
- SDZ driven low after communication.
- Diagnostic driver bound successfully.
- No ALSA playback interface registered.
- No sound cards registered during the experiment.

## Conclusion

Physical TAS2562 I2C communication is verified under
native Linux on the Samsung Galaxy Tab Active3 LTE.

The amplifier GPIO configuration and I2C controller
are functional for the detection experiment.

Speaker playback, audio routing, calibration and
protection remain unvalidated.
