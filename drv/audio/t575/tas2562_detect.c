// SPDX-License-Identifier: GPL-2.0
/*
 * SM-T575 TAS2562 detection-only diagnostic.
 * No ALSA registration or speaker playback.
 */

#include <linux/module.h>
#include <linux/i2c.h>
#include <linux/gpio/consumer.h>
#include <linux/delay.h>
#include <linux/of.h>

#define TAS_PAGE       0x00
#define TAS_POWER      0x02
#define TAS_REVISION   0x7d
#define TAS_MODE_MASK  0x03
#define TAS_SHUTDOWN   0x02

static int t575_tas_detect(struct i2c_client *client)
{
    struct device *dev = &client->dev;
    struct gpio_desc *sdz;
    int rev, power, verify, ret;

    if (client->addr != 0x4c)
        return -ENODEV;

    if (!i2c_check_functionality(client->adapter,
                                I2C_FUNC_SMBUS_BYTE_DATA))
        return -EOPNOTSUPP;

    sdz = devm_gpiod_get(dev, "shutdown", GPIOD_ASIS);
    if (IS_ERR(sdz))
        return dev_err_probe(dev, PTR_ERR(sdz),
                             "SDZ acquisition failed\n");

    if (gpiod_is_active_low(sdz))
        return dev_err_probe(dev, -EINVAL,
                             "Unexpected SDZ polarity\n");

    ret = gpiod_direction_output(sdz, 0);
    if (ret)
        return ret;

    msleep(30);

    dev_info(dev, "T575 detection-only test starting\n");

    gpiod_set_value_cansleep(sdz, 1);
    msleep(30);

    ret = i2c_smbus_write_byte_data(client, TAS_PAGE, 0);
    if (ret < 0)
        goto shutdown;

    power = i2c_smbus_read_byte_data(client, TAS_POWER);
    if (power < 0) {
        ret = power;
        goto shutdown;
    }

    dev_info(dev, "Initial power register: 0x%02x\n", power);

    if ((power & TAS_MODE_MASK) != TAS_SHUTDOWN) {
        dev_err(dev, "Unexpected initial power mode\n");
        ret = -EIO;
        goto shutdown;
    }

    rev = i2c_smbus_read_byte_data(client, TAS_REVISION);
    if (rev < 0) {
        ret = rev;
        goto shutdown;
    }

    ret = i2c_smbus_write_byte_data(
        client, TAS_POWER,
        (power & ~TAS_MODE_MASK) | TAS_SHUTDOWN);

    if (ret < 0)
        goto shutdown;

    verify = i2c_smbus_read_byte_data(client, TAS_POWER);
    if (verify < 0) {
        ret = verify;
        goto shutdown;
    }

    if ((verify & TAS_MODE_MASK) != TAS_SHUTDOWN) {
        ret = -EIO;
        goto shutdown;
    }

    dev_info(dev, "Silicon revision register: 0x%02x\n", rev);
    dev_info(dev, "Shutdown verified: 0x%02x\n", verify);

    ret = 0;

shutdown:
    gpiod_set_value_cansleep(sdz, 0);
    msleep(30);

    dev_info(dev, "SDZ driven low\n");

    if (ret < 0)
        return dev_err_probe(dev, ret,
                             "Amplifier detection failed\n");

    dev_info(dev, "PASS: TAS2562 hardware communication\n");
    dev_info(dev, "No playback interface registered\n");

    return 0;
}

static const struct of_device_id t575_tas_detect_of[] = {
    { .compatible = "ti,tas2562" },
    { }
};

MODULE_DEVICE_TABLE(of, t575_tas_detect_of);

static struct i2c_driver t575_tas_detect_driver = {
    .driver = {
        .name = "t575-tas2562-detect",
        .of_match_table = t575_tas_detect_of,
    },
    .probe = t575_tas_detect,
};

module_i2c_driver(t575_tas_detect_driver);

MODULE_DESCRIPTION("SM-T575 TAS2562 detection-only diagnostic");
MODULE_LICENSE("GPL");
