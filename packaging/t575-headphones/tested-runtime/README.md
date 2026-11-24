# Privacy-redacted SM-T575 headphone runtime

The scripts and unit in this directory are **redacted snapshots** of the
tested live setup. The private user account and UID were substituted with:
`__AUDIO_LOGIN__` and `__AUDIO_UID__`.

The originals are intentionally not republished. The controller sequences
and rollback logic are otherwise preserved, but these sanitized scripts
**cannot execute as-is**. Kernel, module ABI, and TAS2562 speaker safety
must be verified independently.

## Check archived files

```sh
cd packaging/t575-headphones/tested-runtime
sha256sum -c SHA256SUMS
sh -n headphones-managed.sh
sh -n rollback-v2.sh
```

## Render a private local copy on the target tablet

From a checkout of this repository branch, run as the intended, non-root
Phosh/PipeWire account (this example does NOT install or start anything):

```sh
export T575_AUDIO_LOGIN="$(id -un)" T575_AUDIO_UID="$(id -u)"
python3 - <<'PY'
import os, re
from pathlib import Path

login = os.environ["T575_AUDIO_LOGIN"]
uid = os.environ["T575_AUDIO_UID"]
assert re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", login)
assert re.fullmatch(r"[0-9]+", uid)

src = Path("packaging/t575-headphones/tested-runtime")
dst = Path.home() / "t575-headphone-private"
dst.mkdir(mode=0o700, exist_ok=False)
for name in ("headphones-managed.sh", "rollback-v2.sh", "t575-headphones.service"):
    value = (src / name).read_text()
    value = value.replace("__AUDIO_LOGIN__", login).replace("__AUDIO_UID__", uid)
    assert "__AUDIO_" not in value
    f = dst / name
    f.write_text(value)
    f.chmod(0o600)
print("Generated locally:", dst)
PY
```

Do not commit this local rendered directory. This example only prepares
private text files; it deliberately does not install, run or enable a driver.
See [the full bring-up record](../../../docs/audio/t575-headphones-live-2026-11-24.md)
for codec build requirements, rollback tests, and unresolved boot-order work.
