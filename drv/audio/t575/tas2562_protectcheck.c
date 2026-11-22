// SPDX-License-Identifier: GPL-2.0
/*
 * SM-T575 Stage E4C 64-clock silent transport.
 * Registers an ASoC DAI with the amplifier held in shutdown.
 */

#include <linux/module.h>
#include <linux/i2c.h>
#include <linux/gpio/consumer.h>
#include <linux/of.h>
#include <linux/delay.h>
#include <linux/mutex.h>
#include <linux/sysfs.h>
#include <linux/pm.h>
#include <sound/soc.h>
#include <sound/pcm.h>


#define TAS_PAGE       0x00
#define TAS_BOOK       0x7f
#define TAS_POWER      0x02
#define TAS_REVISION   0x7d
#define TAS_TDM_DET    0x11
#define TAS_LIVE0      0x1f
#define TAS_LIVE1      0x20
#define TAS_LATCH0     0x24
#define TAS_LATCH1     0x25


#define TAS_GAIN       0x03
#define TAS_GAIN_MASK  0x3e
#define TAS_DVC_PAGE   0x02
#define TAS_DVC_FIRST  0x0c
#define TAS_MISC       0x04
#define TAS_TDM_CFG2   0x08
#define TAS_RETRY_MASK 0x30

static int t575_configure_shutdown(struct i2c_client *client)
{
    struct device *dev = &client->dev;
    static const u8 attenuation[] = {
        0x00, 0x10, 0x62, 0x4e
    };
    int ret, value, target, i;

    /* Confirm software shutdown before configuration. */
    value = i2c_smbus_read_byte_data(client, TAS_POWER);
    if (value < 0)
        return value;

    if (value != 0x0e)
        return -EIO;

    /* Preserve every bit outside the gain field. */
    value = i2c_smbus_read_byte_data(client, TAS_GAIN);
    if (value < 0)
        return value;

    target = value & ~TAS_GAIN_MASK;

    dev_info(dev, "GAIN before=0x%02x target=0x%02x\n",
             value, target);

    ret = i2c_smbus_write_byte_data(client, TAS_GAIN, target);
    if (ret < 0)
        return ret;

    value = i2c_smbus_read_byte_data(client, TAS_GAIN);
    if (value < 0)
        return value;

    if (value != target)
        return -EIO;

    dev_info(dev, "PASS: minimum gain readback 0x%02x\n",
             value);

    ret = i2c_smbus_write_byte_data(client,
                                    TAS_PAGE, TAS_DVC_PAGE);
    if (ret < 0)
        return ret;

    /* Read original coefficient without changing it. */
    for (i = 0; i < ARRAY_SIZE(attenuation); i++) {
        value = i2c_smbus_read_byte_data(
                    client, TAS_DVC_FIRST + i);
        if (value < 0)
            return value;

        dev_info(dev, "DVC before 0x%02x = 0x%02x\n",
                 TAS_DVC_FIRST + i, value);
    }

    /* MSB first; LSB last. */
    for (i = 0; i < ARRAY_SIZE(attenuation); i++) {
        ret = i2c_smbus_write_byte_data(
                  client, TAS_DVC_FIRST + i,
                  attenuation[i]);

        if (ret < 0)
            return ret;
    }

    for (i = 0; i < ARRAY_SIZE(attenuation); i++) {
        value = i2c_smbus_read_byte_data(
                    client, TAS_DVC_FIRST + i);

        if (value < 0)
            return value;

        if (value != attenuation[i])
            return -EIO;

        dev_info(dev, "DVC verified 0x%02x = 0x%02x\n",
                 TAS_DVC_FIRST + i, value);
    }

    ret = i2c_smbus_write_byte_data(client, TAS_PAGE, 0);
    if (ret < 0)
        return ret;

    value = i2c_smbus_read_byte_data(client, TAS_POWER);
    if (value < 0)
        return value;

    if (value != 0x0e)
        return -EIO;

    dev_info(dev, "PASS: -60 dB coefficient verified\n");
    dev_info(dev, "PASS: software shutdown preserved\n");

    return 0;
}


static DEFINE_MUTEX(protectcheck_lock);
static bool protectcheck_suspended;

static ssize_t protectcheck_store(
    struct device *dev,
    struct device_attribute *attr,
    const char *buf, size_t count)
{
    struct i2c_client *client = to_i2c_client(dev);
    struct gpio_desc *sdz = i2c_get_clientdata(client);
    int ret, value, i;
    int det, live0, live1, latch0, latch1;
    int matches = 0;

    if (!sdz)
        return -ENODEV;

    if (!sysfs_streq(buf, "check"))
        return -EINVAL;

    mutex_lock(&protectcheck_lock);

    if (protectcheck_suspended) {
        mutex_unlock(&protectcheck_lock);
        return -EBUSY;
    }

    gpiod_set_value_cansleep(sdz, 0);
    usleep_range(10000, 12000);

    gpiod_set_value_cansleep(sdz, 1);
    usleep_range(5000, 6000);

    ret = i2c_smbus_write_byte_data(client, TAS_PAGE, 0);
    if (ret < 0)
        goto out;

    ret = i2c_smbus_write_byte_data(client, TAS_BOOK, 0);
    if (ret < 0)
        goto out;

    value = i2c_smbus_read_byte_data(client, TAS_POWER);
    if (value < 0) {
        ret = value;
        goto out;
    }

    if (value != 0x0e) {
        ret = -EIO;
        goto out;
    }

    value = i2c_smbus_read_byte_data(client, TAS_REVISION);
    if (value < 0) {
        ret = value;
        goto out;
    }

    if (value != 0x10) {
        ret = -ENODEV;
        goto out;
    }


    /* Reapply E2 gain and digital attenuation. */
    ret = t575_configure_shutdown(client);
    if (ret)
        goto out;

    /* Disable automatic overcurrent/temperature retries. */
    value = i2c_smbus_read_byte_data(client, TAS_MISC);
    if (value < 0) {
        ret = value;
        goto out;
    }

    value &= ~TAS_RETRY_MASK;

    ret = i2c_smbus_write_byte_data(client, TAS_MISC, value);
    if (ret < 0)
        goto out;

    ret = i2c_smbus_read_byte_data(client, TAS_MISC);
    if (ret < 0)
        goto out;

    if (ret != value) {
        ret = -EIO;
        goto out;
    }

    dev_info(dev, "E4C: automatic fault retries disabled\n");

    /* Configure 32-bit receive words in 32-bit slots. */
    value = i2c_smbus_read_byte_data(client, TAS_TDM_CFG2);
    if (value < 0) {
        ret = value;
        goto out;
    }

    value = (value & ~0x0f) | 0x0e;

    ret = i2c_smbus_write_byte_data(client, TAS_TDM_CFG2, value);
    if (ret < 0)
        goto out;

    ret = i2c_smbus_read_byte_data(client, TAS_TDM_CFG2);
    if (ret < 0)
        goto out;

    if (ret != value) {
        ret = -EIO;
        goto out;
    }

    dev_info(dev, "E4C: TDM_CFG2 verified: %02x\n", value);

    value = i2c_smbus_read_byte_data(client, TAS_POWER);
    if (value != 0x0e) {
        ret = value < 0 ? value : -EIO;
        goto out;
    }

    for (i = 0; i < 10; i++) {
        value = i2c_smbus_read_byte_data(client, TAS_POWER);

        if (value != 0x0e) {
            ret = value < 0 ? value : -EIO;
            goto out;
        }

        det = i2c_smbus_read_byte_data(client, TAS_TDM_DET);
        live0 = i2c_smbus_read_byte_data(client, TAS_LIVE0);
        live1 = i2c_smbus_read_byte_data(client, TAS_LIVE1);
        latch0 = i2c_smbus_read_byte_data(client, TAS_LATCH0);
        latch1 = i2c_smbus_read_byte_data(client, TAS_LATCH1);

        if (det < 0 || live0 < 0 || live1 < 0 ||
            latch0 < 0 || latch1 < 0) {
            ret = -EIO;
            goto out;
        }

        dev_info(dev,
            "E4C sample %d: DET=%02x ratio=%x rate=%x live=%02x/%02x latch=%02x/%02x\n",
            i, det, (det >> 3) & 0xf, det & 7,
            live0, live1, latch0, latch1);

        if (live0 || live1 || latch0 || latch1) {
            ret = -EIO;
            goto out;
        }

        if ((det & 0x7f) == 0x24)
            matches++;

        msleep(20);
    }

    value = i2c_smbus_read_byte_data(client, TAS_POWER);

    if (value != 0x0e) {
        ret = value < 0 ? value : -EIO;
        goto out;
    }

    dev_info(dev,
        "E4C: clock matches %d/10; software shutdown verified\n",
        matches);

    ret = matches == 10 ? count : -EAGAIN;

out:
    gpiod_set_value_cansleep(sdz, 0);
    dev_info(dev, "E4C: hardware shutdown restored\n");

    mutex_unlock(&protectcheck_lock);

    return ret;
}

static DEVICE_ATTR(protectcheck, 0200, NULL, protectcheck_store);

static int t575_protectcheck_startup(
    struct snd_pcm_substream *substream,
    struct snd_soc_dai *dai)
{
    struct gpio_desc *sdz = dev_get_drvdata(dai->dev);

    if (!sdz)
        return -ENODEV;

    mutex_lock(&protectcheck_lock);
    gpiod_set_value_cansleep(sdz, 0);
    mutex_unlock(&protectcheck_lock);

    dev_info(dai->dev,
             "E4C: silent PCM transport; amplifier remains disabled\n");
    return 0;
}

static const struct snd_soc_dai_ops t575_protectcheck_ops = {
    .startup = t575_protectcheck_startup,
};

static struct snd_soc_dai_driver t575_protectcheck_dai = {
    .name = "tas2562-protectcheck",
    .playback = {
        .stream_name = "Playback",
        .channels_min = 2,
        .channels_max = 2,
        .rates = SNDRV_PCM_RATE_48000,
        .formats = SNDRV_PCM_FMTBIT_S32_LE,
    },
    .ops = &t575_protectcheck_ops,
};

static const struct snd_soc_dapm_widget t575_protectcheck_widgets[] = {
    SND_SOC_DAPM_OUTPUT("OUT"),
};

static const struct snd_soc_component_driver t575_protectcheck_component = {
    .name = "tas2562-protectcheck",
    .dapm_widgets = t575_protectcheck_widgets,
    .num_dapm_widgets = ARRAY_SIZE(t575_protectcheck_widgets),
};

static int t575_protectcheck_probe(struct i2c_client *client)
{
    struct device *dev = &client->dev;
    struct gpio_desc *sdz;

    if (client->addr != 0x4c)
        return -ENODEV;

    sdz = devm_gpiod_get(dev, "shutdown", GPIOD_ASIS);
    if (IS_ERR(sdz))
        return dev_err_probe(dev, PTR_ERR(sdz),
                             "SDZ acquisition failed\n");

    if (gpiod_is_active_low(sdz))
        return -EINVAL;

    int ret = gpiod_direction_output(sdz, 0);
    if (ret)
        return ret;

    i2c_set_clientdata(client, sdz);

    dev_info(dev, "Stage E4C: amplifier held in hardware shutdown\n");

    if (!i2c_check_functionality(client->adapter,
                                 I2C_FUNC_SMBUS_BYTE_DATA))
        return -EOPNOTSUPP;

    ret = devm_snd_soc_register_component(
        dev, &t575_protectcheck_component,
        &t575_protectcheck_dai, 1);
    if (ret)
        return ret;

    return device_create_file(dev, &dev_attr_protectcheck);
}

static void t575_protectcheck_shutdown(struct i2c_client *client)
{
    struct gpio_desc *sdz = i2c_get_clientdata(client);

    device_remove_file(&client->dev, &dev_attr_protectcheck);

    mutex_lock(&protectcheck_lock);
    gpiod_set_value_cansleep(sdz, 0);
    mutex_unlock(&protectcheck_lock);
}

static int t575_protectcheck_suspend(struct device *dev)
{
    struct gpio_desc *sdz = dev_get_drvdata(dev);

    mutex_lock(&protectcheck_lock);
    protectcheck_suspended = true;
    gpiod_set_value_cansleep(sdz, 0);
    mutex_unlock(&protectcheck_lock);

    return 0;
}

static int t575_protectcheck_resume(struct device *dev)
{
    struct gpio_desc *sdz = dev_get_drvdata(dev);

    mutex_lock(&protectcheck_lock);
    gpiod_set_value_cansleep(sdz, 0);
    protectcheck_suspended = false;
    mutex_unlock(&protectcheck_lock);

    return 0;
}

static DEFINE_SIMPLE_DEV_PM_OPS(t575_protectcheck_pm,
    t575_protectcheck_suspend, t575_protectcheck_resume);

static const struct of_device_id t575_protectcheck_of[] = {
    { .compatible = "samsung,t575-tas2562-protectcheck" },
    { }
};

MODULE_DEVICE_TABLE(of, t575_protectcheck_of);

static struct i2c_driver t575_protectcheck_driver = {
    .driver = {
        .name = "t575-tas2562-protectcheck",
        .of_match_table = t575_protectcheck_of,
        .pm = pm_sleep_ptr(&t575_protectcheck_pm),
    },
    .probe = t575_protectcheck_probe,
    .remove = t575_protectcheck_shutdown,
    .shutdown = t575_protectcheck_shutdown,
};

module_i2c_driver(t575_protectcheck_driver);

MODULE_DESCRIPTION("SM-T575 E4C shutdown-only protection configuration");
MODULE_LICENSE("GPL");
