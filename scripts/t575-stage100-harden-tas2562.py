#!/usr/bin/env python3

from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("Usage: patch-script /path/to/tas2562.c")

p = Path(sys.argv[1])
s = p.read_text()

def replace(old, new):
    global s
    assert s.count(old) == 1, f"Unexpected source: {old!r}"
    s = s.replace(old, new, 1)

# Propagate device-tree initialization errors.
replace(
    "\\ttas2562_parse_dt(data);".replace("\\t", "\t"),
    "\tret = tas2562_parse_dt(data);\n"
    "\tif (ret)\n"
    "\t\treturn dev_err_probe(dev, ret, "
    '"TAS2562 DT initialization failed\\n");'
)

# Valid default sensing slots must not return ENOENT.
start = s.index("static int tas2562_parse_dt(")
end = s.index("static const struct i2c_device_id", start)

body = s[start:end]

assert body.count("\treturn ret;") == 2
pos = body.rindex("\treturn ret;")
body = body[:pos] + body[pos:].replace(
    "\treturn ret;", "\treturn 0;", 1
)

s = s[:start] + body + s[end:]


# Do not silently discard GPIO acquisition failures.
import re

start = s.index("static int tas2562_parse_dt(")
end = s.index("static const struct i2c_device_id", start)
body = s[start:end]

pattern = (
    r'if \(IS_ERR\(tas2562->sdz_gpio\)\) \{\s*'
    r'if \(PTR_ERR\(tas2562->sdz_gpio\) == -EPROBE_DEFER\)\s*'
    r'return -EPROBE_DEFER;\s*'
    r'tas2562->sdz_gpio = NULL;\s*\}'
)

body, count = re.subn(
    pattern,
    lambda m: (
        "if (IS_ERR(tas2562->sdz_gpio))\n"
        + re.search(r"(?m)^(\t+)if", m.group(0)).group(1)
        + "return PTR_ERR(tas2562->sdz_gpio);"
    ),
    body
)

assert count == 2, f"Expected two GPIO checks, found {count}"

s = s[:start] + body + s[end:]

print("PASS: GPIO acquisition failures propagated")

p.write_text(s)

print("PASS: DT initialization errors propagated")
print("PASS: optional sensing-slot defaults corrected")
print("Experimental compilation copy only")
