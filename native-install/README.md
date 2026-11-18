# SM-T575 native installation — transport foundation

This **does not install Phosh**. It is a deliberately RAM-only transport foundation for a future bounded verified userdata image writer. The ARM64 receiver runs in the existing SM-T575 bring-up initramfs, listens on TCP/23456 and accepts exactly one of up to 1 MiB in-memory bytes per connection. It computes CRC32 and replies; it does not open any disk devices. The host test sends a deterministic 1 MiB payload over the existing USB IPv6 link. It does not send the full disk image.

## Build

Run GitHub Actions workflow **SM-T575 native installer transport (RAM-only)** and download `t575-native-receiver-ram-only`.

## Tablet

With existing Linux diagnostic console accessible, upload `t575-receiver` using the tested `put PATH LEN` transport and launch with `run /tmp/t575-receiver --start`. Double-forking detaches the server from the console's 60-second run limit. The daemon dies when the tablet reboots. Do not use this with Android.

## Mac

Run `python3 native-install/t575-test-transport.py --interface en7` while Linux USB IPv6 console is active. A PASS proves only the 1 MiB RAM transfer and checksum, not raw image-writing safety, disk integrity, EFI handoff or Phosh boot.

## Future writer safety requirements

- Fail closed unless model SM-T575, target `/dev/sda31`, partition name `userdata`, exact 55,461,281,792 byte capacity, 4096-byte logical blocks, and unmounted status are validated at time of writing.
- Authenticate the Mac sender and make the destructive operation an explicit separate mode. Prevent unsolicited network connections from causing a write.
- Add resumable chunk verification and read-back hashes; never infer completion from the amount sent.
- Repair both GPT headers / CRCs on the larger userdata partition before first boot, and validate the EFI System Partition and signed UKI.
- Only then make a separate, destructive install release. The current code deliberately has no write capability.
