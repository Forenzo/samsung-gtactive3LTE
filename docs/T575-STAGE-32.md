# Stage 32 — live FDT status diagnosis

Stage 31 demonstrated that the running SM-T575 exposes a kernel
device-tree filesystem, with several display and reserved-memory
nodes accessible. Its `unavailable` readings for DSIM1, audio and
codecs are ambiguous: the Stage 31 shell command used `head -c`,
which may fail on this particular Android shell. These readings do
**not** show that the nodes are absent or disabled.

Stage 32 uses Android's `cat` for the fixed status files and
differentiates `NODE_MISSING`, `STATUS_ABSENT` (implicit),
`STATUS_DENIED`, `READ_FAILED`, `SHELL_FAILURE` and recognized
status words. It never prints raw property bytes or identifying data.

Run while the rooted tablet is normally operating and authorized for ADB:

```sh
cd ~/samsung-gtactive3LTE
python3 -m py_compile scripts/t575-stage32-runtime-dt-diagnostics.py
python3 scripts/t575-stage32-runtime-dt-diagnostics.py
```

The command is read-only and does not require root. A status can differ
from the BOOT+overlay FDT even when an overlay index matches, due to
bootloader changes or runtime DT exposure differences.

Still blocked: tested non-wiping Download-mode restore, verified
matching original stock firmware, S-Boot scanout handover, first Linux
boot/flash. Never use the upstream Wi-Fi tablet installer on the T575.
