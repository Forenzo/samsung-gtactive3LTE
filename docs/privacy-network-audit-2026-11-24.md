# Network address privacy audit — November 24, 2026

**Status: PARTIAL CLEANUP ONLY. Do not claim this public repository is address-free.**

## Verified audit coverage

- A GitHub Actions read-only full-tree audit examined **38,230 tracked paths on `main`**. It flagged **1,353 files** with potential IPv4/IPv6 literals: 1,301 vendored U-Boot/bootchain, 32 first-party scripts/docs/tests, 15 system-package files, and 5 patch files.
- A second run against this branch, after endpoint refactoring, reported **1,331 candidate files**; the modified first-party console sources no longer contain the device-specific USB link-local literal.
- A separate read-only audit traversed **18 current remote branch heads**, excluding vendored bootchain files for its detailed per-branch report.
- Many matches in vendored code are **not privacy leaks** (protocol constants, test networks, hexadecimal patterns); 127.0.0.1 and QEMU guest networking are generic fixtures. Do not indiscriminately change them.

## Work prepared in draft PR #6

First-party host scripts, Duranium USB debug comments and older Duranium patch examples have been updated to use a **local** environment variable (`GTA3_CONSOLE_ADDR`) instead of embedding the device USB console endpoint. Corresponding tests passed shell/Python syntax and patch-format validation. These changes have **not** been merged to `main` or run on a tablet; downstream patch application and user-configured host scripts require testing.

## Known outstanding exposure

- Multiple active LTE branches still contain numeric private USB host/tablet addresses in `first-gui/*` Python and C diagnostic code, e.g. `first-gui/t575-ipv4.c`, `first-gui/launch-t575-plasma.py`, `first-gui/t575-nfs-rpc-probe.c`, `first-gui/t575-plasma-direct.c`, `first-gui/usb-ipv4-transfer.py`, and `first-gui/*probe*.py`.
- `native-install/t575-send-v4.py` and related preflight tools embed a default console endpoint on certain LTE branches.
- Historical LTE boot/Plasma documentation and first-boot logs had endpoint literals. Several active branches have received forward redaction commits for the documentation. Remaining code still needs a safe **parameterization/rebuild/retest** pass.
- Older historical commits, PR diffs (including removed lines), GitHub Actions logs, release artifacts and external caches **may still reveal original values**. Forward edits alone do not erase old Git object content.
- The current default branch still has hardcoded endpoints until this draft PR is reviewed and merged. The reviewed work is therefore a pending privacy improvement, not completed remediation.

## Required follow-up before declaring clean

1. Inventory first-party `first-gui/`, `native-install/`, and `tools/` endpoints on all active LTE branches. Replace hardcoded device-to-host values with local configuration/arguments, **without changing** network semantics or boot/install safety gates.
2. Validate C compilation, Python syntax, USB console, NFS-assisted boot and native-install dry-run. Do **not** run a flash or change tablet partitions merely for privacy checks.
3. Re-scan changed branch heads and inspect PR diffs specifically for old values on deleted lines.
4. Review history/release artifacts separately; use GitHub-supported sensitive-data removal where applicable. Do not claim permanent erasure from a branch-tip rewrite alone.
5. Keep sensitive endpoints and login names out of public CI logs, scripts, and examples. Store real endpoints only in locally ignored settings.

The full-tree and all-branch read-only scanners are on `audit/ip-literals-20261124`. This document contains **no real device IP addresses**.
