// SPDX-License-Identifier: GPL-2.0-or-later
/*
 * SM-T575 isolated first-boot diagnostic PID 1.
 * Intentionally DOES NOT reuse the T570 initramfs/init.c:
 * no MMIO, /dev/mem, watchdog manipulation, automatic reboots,
 * flash access, filesystem formatting, networking or display takeover.
 *
 * Writes to console only when console exists. On a kernel panic or a
 * missing console, host-based recovery is still required. UNTESTED.
 */
#define _GNU_SOURCE
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <sys/mount.h>
#include <unistd.h>

int main(void)
{
    int fd = open("/dev/console", O_WRONLY | O_NOCTTY);
    if (fd >= 0) {
        static const char msg[] =
            "\nSM-T575 LTE: minimal diagnostic Linux init started\n"
            "No partitions or hardware registers will be modified by this init.\n"
            "This is NOT a graphical desktop or a validated tablet boot.\n";
        (void)write(fd, msg, sizeof(msg) - 1);
        close(fd);
    }
    /* Never try to recover by writing PMU/reset registers. */
    for (;;) pause();
}
