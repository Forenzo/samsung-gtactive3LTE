/* SPDX-License-Identifier: MIT
 * Non-destructive TCP reachability check for NFS-over-USB bring-up.
 * Does not mount, authenticate, issue RPC requests or write disk.
 * Default host: macOS 10.77.57.1 on the SM-T575 USB NCM segment.
 */
#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <netinet/in.h>
#include <poll.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>

static int try_tcp(unsigned short port)
{
    int fd = socket(AF_INET, SOCK_STREAM, 0);
    struct sockaddr_in addr;
    struct pollfd p;
    int saved, error = 0;
    socklen_t len = sizeof(error);
    if (fd < 0) { perror("socket"); return 0; }
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_port = htons(port);
    if (inet_pton(AF_INET, "10.77.57.1", &addr.sin_addr) != 1) {
        close(fd);
        return 0;
    }
    saved = fcntl(fd, F_GETFL, 0);
    if (saved < 0 || fcntl(fd, F_SETFL, saved | O_NONBLOCK) < 0) {
        perror("fcntl");
        close(fd);
        return 0;
    }
    if (connect(fd, (const struct sockaddr *)&addr, sizeof(addr)) == 0) {
        close(fd);
        return 1;
    }
    if (errno != EINPROGRESS) {
        close(fd);
        return 0;
    }
    p.fd = fd;
    p.events = POLLOUT;
    p.revents = 0;
    if (poll(&p, 1, 3000) <= 0 ||
        getsockopt(fd, SOL_SOCKET, SO_ERROR, &error, &len) < 0 ||
        error != 0) {
        close(fd);
        return 0;
    }
    close(fd);
    return 1;
}

int main(void)
{
    const unsigned short ports[] = {111, 2049, 1023};
    const char *const service[] = {"rpcbind", "nfs", "mountd"};
    int ok = 0;
    size_t i;
    puts("SM-T575 to macOS 10.77.57.1: TCP connect-only probe");
    for (i = 0; i < sizeof(ports)/sizeof(ports[0]); i++) {
        int result = try_tcp(ports[i]);
        printf("%s TCP %u: %s\n", service[i], ports[i],
               result ? "REACHABLE" : "UNREACHABLE");
        if (result) ok++;
    }
    printf("%d/3 services reachable; no NFS mount attempted.\n", ok);
    return ok == 3 ? 0 : 1;
}
