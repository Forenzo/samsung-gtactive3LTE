// SPDX-License-Identifier: GPL-2.0-only
/*
 * Samsung Galaxy Tab Active3 LTE (SM-T575)
 * Stage E1: TAS2562 shutdown-only register inspection.
 *
 * No playback, boost configuration or calibration activation.
 */

#include <linux/module.h>
#include <linux/i2c.h>
#include <linux/gpio/consumer.h>
#include <linux/delay.h>
#include <linux/errno.h>

#define TAS_PAGE       0x00
#define TAS_POWER      0x02
#define TAS_REVISION   0x7d
#define TAS_MODE_MASK  0x03
#define TAS_SHUTDOWN   0x02

static const u8 inspect_regs[] = {
    0x02, /* Power control */
    0x03, /* Amplifier gain */
    0x04, /* Misc configuration */
    0x06, /* TDM sample rate */
    0x07, /* TDM timing */
    0x08, /* TDM word length */
    0x09, /* TDM slots */
    0x11, /* TDM detection */
    0x12, /* Limiter */
    0x13, /* Limiter */
    0x14, /* Brownout prevention */
    0x15, /* Brownout prevention */
    0x1a, /* Interrupt mask */
    0x1b, /* Interrupt mask */
    0x1c, /* Interrupt mask */
    0x1f, /* Live interrupt status */
    0x20, /* Live interrupt status */
    0x24, /* Latched interrupt status */
    0x25, /* Latched interrupt status */
    0x38, /* Clock configuration */
    0x3b, /* Battery filter */
    0x40, /* Boost current configuration */
};

static int t575_safeinit_probe(struct i2c_client *client)
{
    struct device *dev = &client->dev;
    struct gpio_desc *sdz;
    int ret, value, i;

    if (client->addr != 0x4c)
        return -ENODEV;

    sdz = devm_gpiod_get(dev, "shutdown", GPIOD_ASIS);
    if (IS_ERR(sdz))
        return PTR_ERR(sdz);

    if (gpiod_is_active_low(sdz))
        return -EINVAL;

    ret = gpiod_direction_output(sdz, 0);
    if (ret)
        return ret;

    i2c_set_clientdata(client, sdz);

    if (!i2c_check_functionality(client->adapter,
                                 I2C_FUNC_SMBUS_BYTE_DATA))
        return -EOPNOTSUPP;

    dev_info(dev, "Stage E: hardware shutdown asserted\n");

    gpiod_set_value_cansleep(sdz, 1);
    usleep_range(5000, 6000);

    ret = i2c_smbus_write_byte_data(client, TAS_PAGE, 0);
    if (ret < 0)
        goto shutdown;

    value = i2c_smbus_read_byte_data(client, TAS_POWER);
    if (value < 0) {
        ret = value;
        goto shutdown;
    }

    if ((value & TAS_MODE_MASK) != TAS_SHUTDOWN) {
        dev_err(dev, "Unexpected power state: 0x%02x\n", value);
        ret = -EIO;
        goto shutdown;
    }

    value = i2c_smbus_read_byte_data(client, TAS_REVISION);
    if (value < 0) {
        ret = value;
        goto shutdown;
    }

    if (value != 0x10) {
        dev_err(dev, "Unexpected revision: 0x%02x\n", value);
        ret = -ENODEV;
        goto shutdown;
    }

    dev_info(dev, "TAS2562 revision: 0x%02x\n", value);

    for (i = 0; i < ARRAY_SIZE(inspect_regs); i++) {
        value = i2c_smbus_read_byte_data(client, inspect_regs[i]);

        if (value < 0) {
            ret = value;
            goto shutdown;
        }

        dev_info(dev, "SAFEINIT reg 0x%02x = 0x%02x\n",
                 inspect_regs[i], value);
    }

    value = i2c_smbus_read_byte_data(client, TAS_POWER);
    if (value < 0) {
        ret = value;
        goto shutdown;
    }

    if ((value & TAS_MODE_MASK) != TAS_SHUTDOWN) {
        ret = -EIO;
        goto shutdown;
    }

    ret = 0;

shutdown:
    gpiod_set_value_cansleep(sdz, 0);

    dev_info(dev, "Stage E: hardware shutdown asserted\n");

    if (ret)
        return dev_err_probe(dev, ret, "SAFEINIT failed\n");

    dev_info(dev, "PASS: shutdown-only register inspection\n");
    return 0;
}

static void t575_safeinit_shutdown(struct i2c_client *client)
{
    struct gpio_desc *sdz = i2c_get_clientdata(client);

    gpiod_set_value_cansleep(sdz, 0);
}

static const struct of_device_id t575_safeinit_of_match[] = {
    { .compatible = "samsung,t575-tas2562-safeinit" },
    { }
};

MODULE_DEVICE_TABLE(of, t575_safeinit_of_match);

static struct i2c_driver t575_safeinit_driver = {
    .driver = {
        .name = "t575-tas2562-safeinit",
        .of_match_table = t575_safeinit_of_match,
    },
    .probe = t575_safeinit_probe,
    .remove = t575_safeinit_shutdown,
    .shutdown = t575_safeinit_shutdown,
};

module_i2c_driver(t575_safeinit_driver);

MODULE_DESCRIPTION("SM-T575 shutdown-only TAS2562 diagnostic");
MODULE_LICENSE("GPL");
