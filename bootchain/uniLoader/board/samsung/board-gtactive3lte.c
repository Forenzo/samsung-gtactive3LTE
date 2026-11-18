/* SPDX-License-Identifier: GPL-2.0 */
/*
 * Samsung Galaxy Tab Active3 LTE (SM-T575) experimental first handoff.
 *
 * S-Boot's framebuffer handover is at 0xca000000, 1200x1920 ARGB8888:
 * confirmed against physical T575 framebuffer inventory. This simplefb
 * registration writes only to the existing framebuffer DRAM; it does NOT
 * copy the Wi-Fi board's DECON_F HW_SW_TRIG_CONTROL MMIO write.
 *
 * A GPIO sample on the physical LTE tablet showed GPA0_DAT 0x3e idle and
 * 0x2e while holding Volume Down, so bit 4 is active-low. Selecting the
 * embedded diagnostic Linux from uniLoader reads hardware registers only.
 *
 * NO watchdog programming, reset reason modification, DECON MMIO writes,
 * storage access or auto-recovery is performed here. If U-Boot hangs,
 * recover manually with Samsung Download Mode and a verified BOOT backup.
 * This board remains EXPERIMENTAL AND NOT YET BOOT TESTED ON SM-T575.
 */
#include <board.h>
#include <util.h>
#include <drivers/framework.h>
#include <lib/simplefb.h>
#include <stdint.h>

#ifdef CONFIG_CHAINLOAD
#include <main/chainload.h>

/* Exynos9810 PMU reset status and GPA0 data; READ ONLY. */
#define T575_PMU_RST_STAT 0x14060404UL
#define T575_GPA0_DAT 0x14050024UL
#define T575_VOL_DOWN (1U << 4)
#define T575_CLUSTER0_WDT_RST (1U << 24)

static inline uint32_t t575_read_reg(unsigned long address)
{
    return *(volatile uint32_t *)address;
}

/* Reject the U-Boot handoff if Volume Down is held or the prior reset
 * reports a cluster-0 watchdog. No key needs to be held during testing.
 * The S-Boot button combination may enter Download Mode on long holds.
 */
static int t575_chain_select(struct chain_info *ci)
{
    unsigned int i;
    int held = 1;

    ci->rst_stat = t575_read_reg(T575_PMU_RST_STAT);
    ci->keys = t575_read_reg(T575_GPA0_DAT);

    for (i = 0; i < 2000; ++i)
        if (t575_read_reg(T575_GPA0_DAT) & T575_VOL_DOWN)
            held = 0;

    if (ci->rst_stat & T575_CLUSTER0_WDT_RST)
        ci->reason |= CHAIN_R_WDT_RESET;
    if (held)
        ci->reason |= CHAIN_R_KEY;

    return !(ci->reason & (CHAIN_R_KEY | CHAIN_R_WDT_RESET));
}
#endif

static struct video_info t575_fb = {
    .format = FB_FORMAT_ARGB8888,
    .width = 1200,
    .height = 1920,
    .stride = 4,
    .scale = 2,
    .address = (void *)0xca000000
};

static const struct device t575_devices[] = {
    { "simplefb", &t575_fb, "fb" }
};

struct board_data board_ops = {
    .name = "samsung-gtactive3lte",
    .ops = {
#ifdef CONFIG_CHAINLOAD
        .chain_select = t575_chain_select,
#endif
    },
    .devices = t575_devices,
    .num_devices = ARRAY_SIZE(t575_devices),
    .quirks = 0
};
