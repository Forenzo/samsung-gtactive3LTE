/* SPDX-License-Identifier: GPL-2.0 */
/*
 * Samsung Galaxy Tab Active3 LTE (SM-T575) -- isolated compile-only board.
 *
 * Do not copy the SM-T570 board's DECON register write or chainload hooks:
 * neither the display handover nor watchdog/reboot behavior has been
 * established on this LTE variant.
 *
 * This board intentionally registers no framebuffer devices or hooks.
 * It is NOT boot-tested, and must not be packed or flashed.
 */
#include <board.h>

struct board_data board_ops = {
	.name = "samsung-gtactive3lte",
	.ops = { 0 },
	.devices = 0,
	.num_devices = 0,
	.quirks = 0
};
