// SPDX-License-Identifier: MIT
/*
 * Touch boost, as Samsung's input_booster does on the stock firmware
 * (docs/BATTERY.md, "Scheduler, cpufreq, boosts"): while a finger or the
 * pen is down (BTN_TOUCH, so a finger held still keeps it), and for TAIL_MS
 * after the release or the last event, each cpufreq policy's frequency
 * floor goes up, so the first frames of a swipe or a tap
 * are drawn at speed instead of after schedutil has noticed the load from
 * the lowest level. Between touches each policy keeps a resting floor.
 *
 *   gtactive3wifi-input-boost [-t TAIL_MS] [-d EVDEV]... POLICY:REST:BOOST...
 *
 * POLICY is a cpufreq policy directory, REST and BOOST are in kHz (0 = the
 * floor found there). Only scaling_min_freq is written: the governor still
 * chooses the frequency and the power profiles keep their caps (a floor
 * above scaling_max_freq is lowered to it). A policy that is not there yet
 * (cpufreq-dt is a module) is picked up at the next change. On SIGTERM
 * each policy gets back the floor found there, unless something else has
 * changed it since our last write (then that value stays). A refused write
 * is logged once until a write to that policy succeeds again.
 *
 * Without -d, every input device that is a touchscreen (INPUT_PROP_DIRECT)
 * or a pen (BTN_TOOL_PEN: wacom_w9000 sets no INPUT_PROP_DIRECT) is
 * watched, including ones that appear later (the touch controller can be
 * re-probed). -d watches the given files instead, without that check (the
 * offline test feeds a FIFO).
 */
#define _GNU_SOURCE	/* ppoll */
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <linux/input.h>
#include <poll.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/inotify.h>
#include <sys/ioctl.h>
#include <time.h>
#include <unistd.h>

#define INPUT_DIR	"/dev/input"
#define MAX_POLICIES	4
#define MAX_DEVS	16
#define LONG_BITS	(8 * sizeof(long))
#define NLONGS(n)	(((n) + LONG_BITS - 1) / LONG_BITS)

struct policy {
	char min_path[PATH_MAX];
	char max_path[PATH_MAX];
	long found;		/* floor before we started, -1 = not read yet */
	long rest, boost;	/* 0 = the floor found */
	long written;		/* our last floor there, -1 = none */
	int failed;		/* a refused write was logged */
};

static struct policy pol[MAX_POLICIES];
static int npol;
/* [0] is the inotify watch on /dev/input (-1 with -d), then the devices */
static struct pollfd pfd[1 + MAX_DEVS];
static char devname[1 + MAX_DEVS][PATH_MAX];
static char down[1 + MAX_DEVS];	/* BTN_TOUCH held on that device */
static int ndev;
static volatile sig_atomic_t stop;

static long long now_ms(void)
{
	struct timespec ts;

	clock_gettime(CLOCK_MONOTONIC, &ts);
	return ts.tv_sec * 1000LL + ts.tv_nsec / 1000000;
}

static long read_khz(const char *path)
{
	char buf[32];
	ssize_t n;
	int fd = open(path, O_RDONLY | O_CLOEXEC);

	if (fd < 0)
		return -1;
	n = read(fd, buf, sizeof(buf) - 1);
	close(fd);
	if (n <= 0)
		return -1;
	buf[n] = 0;
	return strtol(buf, NULL, 10);
}

/* 0, or -1 with errno set: a refused write leaves the floor as it was */
static int write_khz(const char *path, long khz)
{
	char buf[32];
	int len = snprintf(buf, sizeof(buf), "%ld\n", khz);
	int fd = open(path, O_WRONLY | O_TRUNC | O_CLOEXEC), ret = 0;

	if (fd < 0)
		return -1;
	if (write(fd, buf, len) != len)
		ret = -1;
	close(fd);
	return ret;
}

static void set_floors(int boosted)
{
	int i;

	for (i = 0; i < npol; i++) {
		struct policy *p = &pol[i];
		long khz, max;

		if (p->found < 0) {
			p->found = read_khz(p->min_path);
			if (p->found < 0)
				continue;
		}
		khz = boosted ? p->boost : p->rest;
		if (!khz)
			khz = p->found;
		max = read_khz(p->max_path);
		if (max > 0 && khz > max)
			khz = max;
		if (!write_khz(p->min_path, khz)) {
			p->written = khz;
			p->failed = 0;
		} else if (!p->failed) {
			fprintf(stderr, "%s: cannot write %ld: %s\n", p->min_path,
				khz, strerror(errno));
			p->failed = 1;
		}
	}
}

static void restore_floors(void)
{
	int i;

	for (i = 0; i < npol; i++) {
		struct policy *p = &pol[i];
		long now;

		if (p->found < 0 || p->written < 0)
			continue;
		/* ours, or ours lowered to a cap set later: give it back */
		now = read_khz(p->min_path);
		if (now == p->written || now == read_khz(p->max_path))
			write_khz(p->min_path, p->found);
		else
			printf("%s: left at %ld (changed by someone else)\n",
			       p->min_path, now);
	}
}

static int test_bit(const unsigned long *bits, unsigned int bit)
{
	return (bits[bit / LONG_BITS] >> (bit % LONG_BITS)) & 1;
}

static int is_touch(int fd)
{
	unsigned long props[NLONGS(INPUT_PROP_CNT)] = { 0 };
	unsigned long keys[NLONGS(KEY_CNT)] = { 0 };

	if (ioctl(fd, EVIOCGPROP(sizeof(props)), props) >= 0 &&
	    test_bit(props, INPUT_PROP_DIRECT))
		return 1;
	return ioctl(fd, EVIOCGBIT(EV_KEY, sizeof(keys)), keys) >= 0 &&
	       test_bit(keys, BTN_TOOL_PEN);
}

static void add_dev(const char *path, int check)
{
	int fd, i;

	for (i = 1; i <= ndev; i++)
		if (!strcmp(devname[i], path))
			return;
	if (ndev == MAX_DEVS)
		return;
	fd = open(path, O_RDONLY | O_NONBLOCK | O_CLOEXEC);
	if (fd < 0)
		return;
	if (check && !is_touch(fd)) {
		close(fd);
		return;
	}
	ndev++;
	down[ndev] = 0;
	pfd[ndev].fd = fd;
	pfd[ndev].events = POLLIN;
	snprintf(devname[ndev], sizeof(devname[ndev]), "%s", path);
	printf("watching %s\n", path);
	fflush(stdout);
}

static void remove_dev(int i)
{
	close(pfd[i].fd);
	printf("%s is gone\n", devname[i]);
	fflush(stdout);
	for (; i < ndev; i++) {
		pfd[i] = pfd[i + 1];
		memcpy(devname[i], devname[i + 1], sizeof(devname[i]));
		down[i] = down[i + 1];
	}
	ndev--;
}

static void add_input_dev(const char *name)
{
	char path[300];

	if (strncmp(name, "event", 5))
		return;
	snprintf(path, sizeof(path), INPUT_DIR "/%s", name);
	add_dev(path, 1);
}

static void scan_input(void)
{
	struct dirent *e;
	DIR *d = opendir(INPUT_DIR);

	if (!d)
		return;
	while ((e = readdir(d)))
		add_input_dev(e->d_name);
	closedir(d);
}

static void read_inotify(void)
{
	char buf[4096] __attribute__((aligned(__alignof__(struct inotify_event))));
	ssize_t n;

	while ((n = read(pfd[0].fd, buf, sizeof(buf))) > 0) {
		char *p = buf;

		while (p < buf + n) {
			struct inotify_event *ev = (struct inotify_event *)p;

			if (ev->len)
				add_input_dev(ev->name);
			p += sizeof(*ev) + ev->len;
		}
	}
}

/* events read, or -1 once the device is gone (unplugged, re-probed, EOF) */
static int drain(int i)
{
	struct input_event ev[64];
	int count = 0;

	for (;;) {
		ssize_t n = read(pfd[i].fd, ev, sizeof(ev));

		if (n > 0) {
			int k, got = n / sizeof(ev[0]);

			for (k = 0; k < got; k++)
				if (ev[k].type == EV_KEY && ev[k].code == BTN_TOUCH)
					down[i] = ev[k].value != 0;
			count += got;
			continue;
		}
		if (n < 0 && (errno == EAGAIN || errno == EINTR))
			return count;
		/* gone: count what came before it, the next poll removes it */
		return count ? count : -1;
	}
}

static int parse_policy(char *arg)
{
	char *rest = strchr(arg, ':'), *boost;
	struct policy *p = &pol[npol];

	if (!rest || !(boost = strchr(rest + 1, ':')) || npol == MAX_POLICIES)
		return -1;
	*rest++ = 0;
	*boost++ = 0;
	snprintf(p->min_path, sizeof(p->min_path), "%s/scaling_min_freq", arg);
	snprintf(p->max_path, sizeof(p->max_path), "%s/scaling_max_freq", arg);
	p->found = -1;
	p->written = -1;
	p->rest = strtol(rest, NULL, 10);
	p->boost = strtol(boost, NULL, 10);
	printf("%s: resting floor %ld kHz, touched %ld kHz\n", arg, p->rest,
	       p->boost);
	npol++;
	return 0;
}

static int held(void)
{
	int i;

	for (i = 1; i <= ndev; i++)
		if (down[i])
			return 1;
	return 0;
}

static void on_signal(int sig)
{
	(void)sig;
	stop = 1;
}

int main(int argc, char **argv)
{
	long tail = 500;
	long long deadline = 0;
	int boosted = 0, explicit = 0, opt;
	struct sigaction sa = { .sa_handler = on_signal };
	sigset_t block, unblocked;

	pfd[0].fd = -1;
	pfd[0].events = POLLIN;
	while ((opt = getopt(argc, argv, "t:d:")) != -1) {
		switch (opt) {
		case 't':
			tail = strtol(optarg, NULL, 10);
			break;
		case 'd':
			explicit = 1;
			add_dev(optarg, 0);
			break;
		default:
			goto usage;
		}
	}
	for (; optind < argc; optind++)
		if (parse_policy(argv[optind]))
			goto usage;
	if (!npol)
		goto usage;
	printf("boost lasts %ld ms after the last touch event\n", tail);

	/* signals arrive only inside ppoll, so none is lost between checks */
	sigemptyset(&block);
	sigaddset(&block, SIGTERM);
	sigaddset(&block, SIGINT);
	sigprocmask(SIG_BLOCK, &block, &unblocked);
	sigdelset(&unblocked, SIGTERM);
	sigdelset(&unblocked, SIGINT);
	sigaction(SIGTERM, &sa, NULL);
	sigaction(SIGINT, &sa, NULL);

	if (!explicit) {
		pfd[0].fd = inotify_init1(IN_NONBLOCK | IN_CLOEXEC);
		if (pfd[0].fd < 0 ||
		    inotify_add_watch(pfd[0].fd, INPUT_DIR, IN_CREATE) < 0) {
			perror("inotify " INPUT_DIR);
			return 1;
		}
		scan_input();
	}
	fflush(stdout);
	set_floors(0);

	while (!stop) {
		struct timespec ts, *timeout = NULL;
		int touched = 0, i, r;

		/* while a contact is down the boost waits for its release */
		if (boosted && !held()) {
			long long left = deadline - now_ms();

			if (left < 0)
				left = 0;
			ts.tv_sec = left / 1000;
			ts.tv_nsec = (left % 1000) * 1000000;
			timeout = &ts;
		}
		r = ppoll(pfd, 1 + ndev, timeout, &unblocked);
		if (r < 0) {
			if (errno == EINTR)
				continue;
			perror("ppoll");
			break;
		}
		if (r == 0) {
			set_floors(0);
			boosted = 0;
			continue;
		}
		if (pfd[0].fd >= 0 && pfd[0].revents)
			read_inotify();
		/* backwards: removing shifts only entries already handled */
		for (i = ndev; i >= 1; i--) {
			int n;

			if (!pfd[i].revents)
				continue;
			n = drain(i);
			if (n < 0)
				remove_dev(i);
			else if (n > 0)
				touched = 1;
		}
		if (touched) {
			if (!boosted)
				set_floors(1);
			boosted = 1;
			deadline = now_ms() + tail;
		}
	}
	restore_floors();
	return 0;

usage:
	fprintf(stderr, "usage: %s [-t TAIL_MS] [-d EVDEV]... "
		"POLICY:REST_KHZ:BOOST_KHZ...\n", argv[0]);
	return 2;
}
