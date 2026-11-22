# SM-T575 Audio Stage E1

Date: 2026-11-22

Physical TAS2562 shutdown-only inspection: PASS

- Kernel: 7.3.0 #27-postmarketOS
- CI run: 44996337525
- I2C device: 4-004c
- Revision: 0x10
- Registers inspected: 22
- Playback not activated
- Final hardware shutdown asserted

## Physical register baseline

| Register | Value |
|---|---|
| `0x02` | `0x0e` |
| `0x03` | `0x20` |
| `0x04` | `0xc6` |
| `0x06` | `0x09` |
| `0x07` | `0x02` |
| `0x08` | `0x0a` |
| `0x09` | `0x10` |
| `0x11` | `0x7f` |
| `0x12` | `0x12` |
| `0x13` | `0x76` |
| `0x14` | `0x01` |
| `0x15` | `0x2e` |
| `0x1a` | `0xfc` |
| `0x1b` | `0xa6` |
| `0x1c` | `0xdf` |
| `0x1f` | `0x00` |
| `0x20` | `0x00` |
| `0x24` | `0x00` |
| `0x25` | `0x00` |
| `0x38` | `0x0d` |
| `0x3b` | `0x58` |
| `0x40` | `0x76` |

## Final GPIO state

```text
pin 16 (gpm40-0) 0:gpm40  CON(0x1) DAT(0x0) PUD(0x1) DRV(0x0)
```

The baseline does not establish safe speaker
playback limits or reproduce Samsung SmartPA.

BOOST_CFG4 returned 0x76; investigate before
changing boost configuration.
