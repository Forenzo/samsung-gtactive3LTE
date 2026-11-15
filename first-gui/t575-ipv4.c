/* SPDX-License-Identifier: MIT
 * SM-T575 diagnostic test: assign only IPv4 address/netmask to usb0.
 * No routes, gateway, DNS, interface down, flash or file writes.
 * The known working IPv6 link-local debug console remains in place.
 * Compile for ARM64 Linux with aarch64-linux-gnu-gcc -static.
 */
#include <arpa/inet.h>
#include <errno.h>
#include <net/if.h>
#include <netinet/in.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <unistd.h>

static int set_addr(int fd, unsigned long request, const char *address)
{
    struct ifreq req;
    struct sockaddr_in sin;
    memset(&req, 0, sizeof(req));
    memset(&sin, 0, sizeof(sin));
    strncpy(req.ifr_name, "usb0", IFNAMSIZ - 1);
    sin.sin_family = AF_INET;
    if (inet_pton(AF_INET, address, &sin.sin_addr) != 1) {
        fprintf(stderr, "Invalid IPv4 address: %s\n", address);
        return -1;
    }
    memcpy(&req.ifr_addr, &sin, sizeof(sin));
    if (ioctl(fd, request, &req) < 0) {
        perror(request == SIOCSIFADDR ? "SIOCSIFADDR" : "SIOCSIFNETMASK");
        return -1;
    }
    return 0;
}

int main(int argc, char **argv)
{
    int fd;
    struct ifreq probe;
    if (argc != 2 || strcmp(argv[1], "--apply-usb-only") != 0) {
        fprintf(stderr, "Usage: %s --apply-usb-only\n", argv[0]);
        fprintf(stderr, "Sets usb0 IPv4 10.77.57.2/30; never touches routes or storage.\n");
        return 2;
    }
    fd = socket(AF_INET, SOCK_DGRAM, 0);
    if (fd < 0) { perror("socket"); return 1; }
    memset(&probe, 0, sizeof(probe));
    strncpy(probe.ifr_name, "usb0", IFNAMSIZ - 1);
    if (ioctl(fd, SIOCGIFFLAGS, &probe) < 0) {
        perror("usb0 not present");
        close(fd);
        return 1;
    }
    if (!(probe.ifr_flags & IFF_UP)) {
        fprintf(stderr, "usb0 is not UP; refusing configuration\n");
        close(fd);
        return 1;
    }
    if (set_addr(fd, SIOCSIFADDR, "10.77.57.2") < 0 ||
        set_addr(fd, SIOCSIFNETMASK, "255.255.255.252") < 0) {
        close(fd);
        return 1;
    }
    puts("USB0 IPv4: 10.77.57.2 / 255.255.255.252");
    puts("IPv6 diagnostic console and routing unchanged.");
    close(fd);
    return 0;
}
